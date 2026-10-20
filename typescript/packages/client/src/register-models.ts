import { z } from "zod";
import { ApiError } from "./transport.js";

const text = z.string().nullable().optional();
const integer = z.coerce.number().int().nullable().optional();
export const AssignorSchema = z.looseObject({
  assignorName: z.string(),
  executionDate: text,
  acknowledgementDate: text,
});
export const PatentPropertySchema = z
  .looseObject({
    sequenceNumber: integer,
    propertySequenceNumber: integer,
    applicationNumber: text,
    fillingDate: text,
    filingDate: text,
    patentNumber: text,
    publicationNumber: text,
    publicationDate: text,
    pctNumber: text,
    internationalRegistrationNumber: text,
    internationalPublicationDate: text,
    inventionTitle: text,
    inventors: text,
    issueDate: text,
  })
  .transform((property) => ({
    ...property,
    sequenceNumber: property.sequenceNumber ?? property.propertySequenceNumber,
    filingDate: property.filingDate ?? property.fillingDate,
  }));
export const AssignmentRecordSchema = z
  .looseObject({
    reelNumber: z.coerce.number().int(),
    frameNumber: z.coerce.number().int(),
    assignorExecutionDate: text,
    mailDate: text,
    recorded: text,
    correspondentName: text,
    assignors: z.array(AssignorSchema).default([]),
    assignees: z.array(z.string()).default([]),
    conveyance: text,
    conveyanceCode: integer,
    noOfProperties: z.number().int().default(0),
    properties: z.array(PatentPropertySchema).default([]),
  })
  .transform((record) => ({
    ...record,
    reelFrame: `${record.reelNumber}/${record.frameNumber}`,
  }));
export const AssignmentDetailSchema = z.looseObject({
  assignment: z.record(z.string(), z.unknown()),
  noOfProperties: z.number().int().default(0),
  properties: z.array(PatentPropertySchema).default([]),
});
export const TrademarkPropertySchema = z.looseObject({
  sequenceNumber: integer,
  serialNumber: integer,
  registrationNumber: integer,
  mark: text,
  currentOwner: text,
  registrantName: text,
  applicationFilingDate: text,
  registrationDate: text,
  internationalRegistrationNumber: text,
});
export const TrademarkAssignmentRecordSchema = z
  .looseObject({
    reelNumber: z.coerce.number().int(),
    frameNumber: z.union([z.string(), z.number()]).transform(String),
    assignorExecutionDate: text,
    correspondentName: text,
    domesticRepresentative: text,
    assignors: z.array(AssignorSchema).default([]),
    assignees: z.array(z.string()).default([]),
    noOfProperties: z.number().int().default(0),
    properties: z.array(TrademarkPropertySchema).default([]),
  })
  .transform((record) => ({
    ...record,
    reelFrame: `${record.reelNumber}/${record.frameNumber}`,
  }));
export type AssignmentRecord = z.infer<typeof AssignmentRecordSchema>;
export type AssignmentDetail = z.infer<typeof AssignmentDetailSchema>;
export type TrademarkAssignmentRecord = z.infer<
  typeof TrademarkAssignmentRecordSchema
>;
export type Assignor = z.infer<typeof AssignorSchema>;
export type PatentProperty = z.infer<typeof PatentPropertySchema>;
export type TrademarkProperty = z.infer<typeof TrademarkPropertySchema>;
export function parseRegister<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success)
    throw new ApiError(
      "USPTO returned an invalid register response.",
      200,
      "INVALID_RESPONSE",
    );
  return result.data;
}
export function nonnegative(value: number, name: string) {
  if (!Number.isSafeInteger(value) || value < 0)
    throw new RangeError(`${name} must be a nonnegative integer.`);
  return value;
}
