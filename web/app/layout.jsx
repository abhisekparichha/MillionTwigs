import "./globals.css"

export const metadata = {
  title: "MillionTwigs — Satellite Tree & Vegetation Analysis",
  description:
    "Detect, count, and track trees from ISRO and Sentinel-2 satellite imagery. "
    + "Open-source pipeline using DeepForest, U-Net, NDVI, and temporal change detection.",
  keywords: ["satellite", "tree detection", "NDVI", "ISRO", "vegetation", "remote sensing"],
  openGraph: {
    title: "MillionTwigs",
    description: "Satellite-based tree counting and vegetation change detection.",
    type: "website",
  },
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900 antialiased">{children}</body>
    </html>
  )
}
