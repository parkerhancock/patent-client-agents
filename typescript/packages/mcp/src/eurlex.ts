import {
  EU_IP_LEGISLATION,
  EURLEX_IP_SUBJECTS,
  type EurlexClient,
  type EurlexLanguage,
  type EurlexSubject,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

/** Text past this many characters goes to an artifact, as the corpus tools do. */
const INLINE_CHARACTERS = 32_000;
const SUBJECTS = Object.keys(EURLEX_IP_SUBJECTS) as [
  EurlexSubject,
  ...EurlexSubject[],
];
const TOPICS = [...new Set(EU_IP_LEGISLATION.map((act) => act.topic))] as [
  string,
  ...string[],
];
const LANGUAGE_CODES = [
  "en",
  "fr",
  "de",
  "es",
  "it",
  "nl",
  "pt",
  "pl",
  "sv",
  "da",
  "fi",
  "el",
  "cs",
  "hu",
  "ro",
  "bg",
  "sk",
  "sl",
  "hr",
  "et",
  "lv",
  "lt",
  "mt",
  "ga",
] as const;
const eurlexUrl = (celex: string) =>
  `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${celex}`;

/** EU IP case law and legislation from CELLAR, the repository behind EUR-Lex. No credentials. */
export function registerEurlexTools(
  server: FastMCP,
  client: EurlexClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_eu_ip_case_law",
      description:
        "Search Court of Justice and General Court case law on intellectual property (trade marks, designs, copyright, patents and SPCs, plant varieties), newest first, from CELLAR, the repository behind EUR-Lex.\n\nFilter by IP subject, court, document type (judgment, order, Advocate General's opinion), date range and words in the English title (heading, parties and subject keywords). Each case carries its CELEX number, ECLI, date and title. The General Court's EUIPO appeals dominate the trade-mark subject.\n\nRelated tools: `get_eurlex_document` for a case's text; `list_eu_ip_legislation` for the regulations and directives the cases apply.",
      input: z.object({
        words: z
          .string()
          .trim()
          .max(200)
          .nullable()
          .default(null)
          .describe(
            "Words that must all appear in the English title, e.g. 'likelihood of confusion' or 'supplementary protection certificate'.",
          ),
        subjects: z
          .array(z.enum(SUBJECTS))
          .nullable()
          .default(null)
          .describe(`IP subjects (default: all): ${SUBJECTS.join(", ")}.`),
        court: z
          .enum(["court_of_justice", "general_court"])
          .nullable()
          .default(null)
          .describe("Limit to one court."),
        document_type: z
          .enum(["judgment", "order", "opinion"])
          .nullable()
          .default(null)
          .describe(
            "'judgment', 'order', or 'opinion' (of an Advocate General).",
          ),
        date_from: z
          .string()
          .regex(/^\d{4}-\d{2}-\d{2}$/)
          .nullable()
          .default(null)
          .describe("Earliest date, YYYY-MM-DD."),
        date_to: z
          .string()
          .regex(/^\d{4}-\d{2}-\d{2}$/)
          .nullable()
          .default(null)
          .describe("Latest date, YYYY-MM-DD."),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Cases to return (at most 100)."),
        offset: z.number().int().min(0).default(0).describe("Cases to skip."),
      }),
    },
    async (input) => {
      const result = await client.searchCaseLaw({
        words: input.words,
        subjects: input.subjects,
        court: input.court,
        documentType: input.document_type,
        dateFrom: input.date_from,
        dateTo: input.date_to,
        limit: input.limit,
        offset: input.offset,
      });
      const items = result.cases.map((item) => ({
        ...item,
        eurlex_url: eurlexUrl(item.celex),
      }));
      const shown = items.length
        ? `cases ${result.offset + 1}-${result.offset + items.length}`
        : "no cases";
      return {
        ...listEnvelope(
          `EU IP case law — ${result.total.toLocaleString("en-US")} matches${input.words ? ` for \`${input.words}\`` : ""}, returned ${shown}.`,
          items,
          result.provenance,
        ),
        more_available: result.more_available,
      };
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_eurlex_document",
      description:
        "Fetch one EU document by CELEX number: a judgment ('62025TJ0786'), order, Advocate General's opinion, regulation or directive ('32017R1001'), or a consolidated version ('02002R0006-20260701').\n\nReturns CELLAR's metadata (title, date, ECLI, in-force flag, and the latest consolidated version for an act) and the document's text. Text up to 32,000 characters is inline; longer text is delivered as a downloadable artifact. Consolidated versions are documentation tools without legal effect; the Official Journal text is authoritative. Some consolidated versions exist only as PDF, and fetching them reports that no HTML text exists.\n\nRelated tools: `search_eu_ip_case_law`, `list_eu_ip_legislation`.",
      input: z.object({
        celex: z
          .string()
          .trim()
          .min(5)
          .max(40)
          .describe("CELEX number, e.g. '62025TJ0786' or '32017R1001'."),
        language: z
          .enum(LANGUAGE_CODES)
          .default("en")
          .describe(
            "Language of the text (default 'en'); some judgments exist only in some languages.",
          ),
      }),
    },
    async ({ celex, language }) => {
      const { data, provenance } = await client.getDocument(
        celex,
        language as EurlexLanguage,
      );
      const { text, ...metadata } = data;
      const details: Record<string, unknown> = {
        ...metadata,
        eurlex_url: eurlexUrl(data.celex),
        text_length: text.length,
      };
      if (text.length <= INLINE_CHARACTERS) details.text = text;
      else
        details.document = await downloadResult(
          new TextEncoder().encode(text),
          `eurlex-${data.celex}-${language}.txt`,
          "text/plain",
          provenance,
        );
      return detailEnvelope(
        `**${data.celex}**${data.title ? ` — ${data.title.split("#")[0]?.trim()}` : ""}${data.latest_consolidated ? `\nLatest consolidated version: ${data.latest_consolidated.celex}.` : ""}`,
        details,
        provenance,
      );
    },
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_eu_ip_legislation",
      description:
        "List the core EU intellectual-property regulations and directives — trade marks, designs, the unitary patent, SPCs, biotech, trade secrets, enforcement, copyright, geographical indications, plant varieties — with CELLAR's title, date, in-force flag and latest consolidated version.\n\nCELLAR marks an act no longer in force once it is superseded or, for an amending act, once its amendments apply. Use the consolidated version for the text in force.\n\nRelated tools: `get_eurlex_document` for an act's text.",
      input: z.object({
        topic: z
          .enum(TOPICS)
          .nullable()
          .default(null)
          .describe(`Limit to one topic: ${TOPICS.join(", ")}.`),
      }),
    },
    async ({ topic }) => {
      const { acts, provenance } = await client.listLegislation(topic as never);
      return listEnvelope(
        `EU IP legislation${topic ? ` (${topic})` : ""} — ${acts.length} acts.`,
        acts.map((act) => ({ ...act, eurlex_url: eurlexUrl(act.celex) })),
        provenance,
      );
    },
  );
}
