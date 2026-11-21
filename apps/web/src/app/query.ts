import { ApiError } from "@openvietgis/client-sdk";
import {
  MutationCache,
  QueryCache,
  QueryClient
} from "@tanstack/react-query";

function revalidateSessionOnUnauthorized(error: unknown) {
  if (!(error instanceof ApiError) || error.status !== 401) return;
  void queryClient.invalidateQueries({ queryKey: ["me"] });
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.queryKey[0] === "me") return;
      revalidateSessionOnUnauthorized(error);
    }
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      revalidateSessionOnUnauthorized(error);
    }
  }),
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 15_000
    }
  }
});
