import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import { AppRoutes } from "./routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
        <Toaster
          theme="dark"
          position="bottom-right"
          toastOptions={{
            className: "!bg-zinc-900 !text-zinc-100 !border-zinc-800",
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
