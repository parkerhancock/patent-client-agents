import type {
  JpoClient,
  JpoDocumentKind,
  JpoIpType,
} from "../packages/client/src/jpo.js";

const API = "https://ip-data.jpo.go.jp/api/";
const DOC_KINDS: Record<string, JpoDocumentKind> = {
  app_doc_cont_opinion_amendment: "application",
  app_doc_cont_refusal_reason_decision: "mailed",
  app_doc_cont_refusal_reason: "refusal",
};

/** The client call that issues a recorded request, and the value to compare with Python's. */
export function operationFor(
  uri: string,
): (client: JpoClient) => Promise<unknown> {
  const [ip, , endpoint, ...rest] = uri.slice(API.length).split("/") as [
    JpoIpType,
    string,
    string,
    ...string[],
  ];
  const number = decodeURIComponent(rest.at(-1) ?? "");
  const data = async (call: Promise<{ data: unknown }>) => (await call).data;
  const docKind = DOC_KINDS[endpoint];
  if (docKind)
    return async (c) =>
      (await c.getDocuments(ip, docKind, number)).data as unknown;
  switch (endpoint) {
    case "app_progress":
      return (c) => data(c.getProgress(ip, number));
    case "app_progress_simple":
      return (c) => data(c.getProgress(ip, number, { simple: true }));
    case "priority_right_app_info":
      return (c) => data(c.getPriorityInfo(ip, number));
    case "applicant_attorney_cd":
      return (c) => data(c.getApplicantByCode(ip, number));
    case "applicant_attorney":
      return (c) => data(c.getApplicantByName(ip, number));
    case "case_number_reference":
      return (c) =>
        data(c.getNumberReference(ip, rest[0] as "application", number));
    case "cite_doc_info":
      return (c) => data(c.getPatentCitedDocuments(number));
    case "registration_info":
      return (c) => data(c.getRegistrationInfo(ip, number));
    case "jpp_fixed_address":
      return (c) => data(c.getJplatpatUrl(ip, number));
    case "pct_national_phase_application_number":
      return (c) =>
        data(
          c.getPatentPctNationalPhase(
            rest[0] as "international_application",
            number,
          ),
        );
    case "divisional_app_info":
      return (c) => data(c.getPatentDivisionalInfo(number));
  }
  throw new Error(`Unmapped JPO endpoint: ${endpoint}`);
}
