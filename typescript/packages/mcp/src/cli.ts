import { z } from "zod";
import { createServer } from "./index.js";

export function configurationFromEnv(env: Record<string, string | undefined>) {
  const transport = z
    .enum(["stdio", "http"])
    .parse(env.MCP_TRANSPORT ?? "stdio");
  const port = z.coerce
    .number()
    .int()
    .min(1)
    .max(65535)
    .parse(env.MCP_PORT ?? "3000");
  const auth =
    transport === "http"
      ? z
          .object({
            jwksUri: z
              .string()
              .url()
              .refine(
                (value) => new URL(value).protocol === "https:",
                "JWKS URL must use HTTPS.",
              ),
            issuer: z.string().url(),
            audience: z.string().min(1),
          })
          .parse({
            jwksUri: env.MCP_JWKS_URL,
            issuer: env.MCP_ISSUER,
            audience: env.MCP_AUDIENCE,
          })
      : undefined;
  return { transport, port, host: env.MCP_HOST ?? "127.0.0.1", auth };
}

if (import.meta.main) {
  const { auth, ...runtime } = configurationFromEnv(process.env);
  const server = createServer(auth ? { auth } : {});
  await server.run({ ...runtime, stateless: true });
}
