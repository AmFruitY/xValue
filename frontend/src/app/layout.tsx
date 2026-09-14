import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "xVALUE — Football valuation intelligence",
  description:
    "Explainable football market-value estimates for scouting and recruitment decisions.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
