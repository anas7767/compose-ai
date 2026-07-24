import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";

import { AppProviders } from "@/components/providers/app-providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "Compose AI",
  description: "AI-powered building architecture platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-dvh bg-background text-foreground antialiased">
        <ClerkProvider
          appearance={{
            variables: {
              colorBackground: "#17171b",
              colorInputBackground: "#202026",
              colorInputText: "#f7f7f8",
              colorPrimary: "#8b5cf6",
              colorText: "#f7f7f8",
              colorTextSecondary: "#a7a7b2",
              borderRadius: "0.5rem",
              fontFamily: 'Inter, "SF Pro Text", "Segoe UI", ui-sans-serif, system-ui, sans-serif',
            },
            elements: {
              cardBox: "border border-border shadow-lg",
              formButtonPrimary: "bg-primary text-primary-foreground hover:bg-primary/90",
              footerActionLink: "text-primary hover:text-primary/90",
            },
          }}
        >
          <AppProviders>{children}</AppProviders>
        </ClerkProvider>
      </body>
    </html>
  );
}
