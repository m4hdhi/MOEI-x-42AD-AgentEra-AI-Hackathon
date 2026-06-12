/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/proxy/:path*",
        destination: `${process.env.API_INTERNAL_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
