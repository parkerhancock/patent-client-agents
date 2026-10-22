/** Types for http-cache-semantics 4.3.0, which ships JSDoc but no declarations. */
declare module "http-cache-semantics" {
  namespace CachePolicy {
    interface Request {
      url?: string;
      method?: string;
      headers: Record<string, string>;
    }
    interface Response {
      status?: number;
      headers: Record<string, string>;
    }
    interface Options {
      shared?: boolean;
      cacheHeuristic?: number;
      immutableMinTimeToLive?: number;
      ignoreCargoCult?: boolean;
    }
    interface Evaluation {
      response: { headers: Record<string, string>; status: number } | undefined;
      revalidation:
        | { headers: Record<string, string>; synchronous: boolean }
        | undefined;
    }
    interface Revalidated {
      policy: CachePolicy;
      modified: boolean;
      matches: boolean;
    }
    type CachePolicyObject = Record<string, unknown>;
  }
  class CachePolicy {
    constructor(
      request: CachePolicy.Request,
      response: CachePolicy.Response,
      options?: CachePolicy.Options,
    );
    storable(): boolean;
    evaluateRequest(request: CachePolicy.Request): CachePolicy.Evaluation;
    revalidationHeaders(request: CachePolicy.Request): Record<string, string>;
    revalidatedPolicy(
      request: CachePolicy.Request,
      response: CachePolicy.Response,
    ): CachePolicy.Revalidated;
    responseHeaders(): Record<string, string>;
    status(): number;
    timeToLive(): number;
    age(): number;
    maxAge(): number;
    stale(): boolean;
    toObject(): CachePolicy.CachePolicyObject;
    static fromObject(object: CachePolicy.CachePolicyObject): CachePolicy;
  }
  export = CachePolicy;
}
