import type { Metadata } from "next";
import { Inter, Montserrat } from "next/font/google";

import { Provedores } from "@/components/provedores";

import "./globals.css";

// Montserrat: mesma geometria do nome na logo (títulos). Inter: leitura confortável em tabelas e formulários.
const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Concept Vistos", template: "%s · Concept Vistos" },
  description: "Acompanhamento dos processos de visto e passaporte da Concept Vistos.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      suppressHydrationWarning
      className={`${montserrat.variable} ${inter.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <Provedores>{children}</Provedores>
      </body>
    </html>
  );
}
