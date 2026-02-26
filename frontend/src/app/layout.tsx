import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SafeHome — 안전한 부동산 거래의 시작",
  description: "AI 기반 부동산 매물 신뢰도 분석 및 전세사기 위험 탐지 시스템",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md">
          <div className="mx-auto flex h-14 max-w-4xl items-center justify-between px-4">
            <a href="/" className="flex items-center gap-2 text-lg font-bold text-gray-900">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm text-white">
                🏠
              </span>
              SafeHome
            </a>
            <span className="text-xs text-gray-400">AI 매물 신뢰도 분석</span>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        <footer className="border-t border-gray-100 py-6 text-center text-xs text-gray-400">
          SafeHome — 안전한 부동산 거래의 시작
        </footer>
      </body>
    </html>
  );
}
