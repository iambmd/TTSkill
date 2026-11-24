import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {};

// Reads i18n/request.ts: the locale comes from a cookie, not the URL.
export default createNextIntlPlugin()(nextConfig);
