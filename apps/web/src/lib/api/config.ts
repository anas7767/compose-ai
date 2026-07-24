const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

if (!configuredApiBaseUrl) {
  throw new Error("NEXT_PUBLIC_API_BASE_URL is required.");
}

export const apiBaseUrl = configuredApiBaseUrl.replace(/\/$/, "");
