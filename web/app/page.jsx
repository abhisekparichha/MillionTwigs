"use client"

// ── MillionTwigs Landing Page ──────────────────────────────────────────────
// Deployed on Vercel. Interactive demo runs on Hugging Face Spaces (Streamlit).
// Update DEMO_URL below once you've deployed to Hugging Face / Render.

const DEMO_URL    = "https://huggingface.co/spaces/YOUR_USERNAME/milliontwigs"
const GITHUB_URL  = "https://github.com/abhisekparichha/milliontwigs"
const DOCS_URL    = `${GITHUB_URL}#readme`

// ── Data ───────────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: "🛰️",
    title: "ISRO + Sentinel-2 Data",
    body: "Downloads from ISRO Bhuvan (LISS-IV 5.8 m, Cartosat-3 0.25 m), Sentinel-2 (10 m), and Landsat (30 m). Step-by-step guide included.",
  },
  {
    icon: "🌿",
    title: "Vegetation Indices",
    body: "NDVI (Tucker 1979), EVI (Huete 2002), NDRE (red-edge), SAVI, MSAVI2, NDWI, NBR, and LAI estimation — all computed from raw satellite bands.",
  },
  {
    icon: "🌳",
    title: "Tree Crown Detection",
    body: "DeepForest CNN (Weinstein 2020) for ≤1 m imagery, U-Net segmentation (Ronneberger 2015) for 5–10 m, watershed for medium resolution.",
  },
  {
    icon: "📊",
    title: "Tree Count Estimation",
    body: "Allometric scaling (Jucker 2017) estimates tree count from canopy area with 95% confidence intervals when individual crowns can't be resolved.",
  },
  {
    icon: "🔄",
    title: "Change Detection",
    body: "Change Vector Analysis (Malila 1980) and Post-Classification Comparison detect vegetation gain and loss between any two time periods.",
  },
  {
    icon: "🗺️",
    title: "Interactive Maps",
    body: "Folium-based Leaflet maps overlaid with NDVI, gain/loss masks, and detected tree crown polygons exportable as GeoJSON.",
  },
]

const SOURCES = [
  { name: "ISRO Bhuvan",    res: "5.8 m",  free: true,  note: "LISS-IV, best for India" },
  { name: "Cartosat-3",     res: "0.25 m", free: false, note: "RESPOND / Antrix programme" },
  { name: "Sentinel-2",     res: "10 m",   free: true,  note: "Global, 5-day revisit" },
  { name: "Landsat 8/9",    res: "30 m",   free: true,  note: "Archive from 1984" },
  { name: "GEDI LiDAR",     res: "25 m",   free: true,  note: "Canopy height from NASA" },
  { name: "Hansen GFC",     res: "30 m",   free: true,  note: "Annual forest loss/gain" },
]

const PIPELINE = [
  { step: "01", label: "Configure AOI",    desc: "Set bounding box, date range, and sensor in config.yaml" },
  { step: "02", label: "Download imagery", desc: "GEE / Bhuvan / Copernicus — automatic or manual" },
  { step: "03", label: "Compute indices",  desc: "NDVI, EVI, NDRE processed on each scene" },
  { step: "04", label: "Detect trees",     desc: "DeepForest / U-Net / Watershed depending on resolution" },
  { step: "05", label: "Change detection", desc: "CVA compares past vs present — gain/loss map + count delta" },
  { step: "06", label: "Export report",    desc: "HTML map, PNG chart, JSON summary, GeoJSON crowns" },
]

// ── Components ─────────────────────────────────────────────────────────────

function Navbar() {
  return (
    <nav className="fixed top-0 inset-x-0 z-50 bg-white/90 backdrop-blur border-b border-gray-100">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <span className="text-xl font-bold text-forest-800">🌳 MillionTwigs</span>
        <div className="flex items-center gap-6 text-sm font-medium text-gray-600">
          <a href="#features"  className="hover:text-forest-700 transition-colors hidden sm:block">Features</a>
          <a href="#pipeline"  className="hover:text-forest-700 transition-colors hidden sm:block">Pipeline</a>
          <a href="#data"      className="hover:text-forest-700 transition-colors hidden sm:block">Data</a>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer"
             className="flex items-center gap-1.5 hover:text-forest-700 transition-colors">
            <GithubIcon /> GitHub
          </a>
          <a href={DEMO_URL} target="_blank" rel="noreferrer"
             className="px-4 py-1.5 bg-forest-700 text-white rounded-full hover:bg-forest-800 transition-colors">
            Live Demo
          </a>
        </div>
      </div>
    </nav>
  )
}

function Hero() {
  return (
    <section className="pt-32 pb-24 px-6 bg-gradient-to-b from-forest-50 to-white text-center">
      <div className="max-w-4xl mx-auto">
        <div className="fade-up inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-forest-100 text-forest-800 text-sm font-medium mb-6">
          🛰️ Powered by ISRO · Sentinel-2 · Google Earth Engine
        </div>
        <h1 className="fade-up delay-1 text-5xl sm:text-6xl font-extrabold text-forest-900 leading-tight mb-6">
          Count every tree.<br/>Track every change.
        </h1>
        <p className="fade-up delay-2 text-xl text-gray-600 max-w-2xl mx-auto mb-10">
          Open-source satellite analysis pipeline for detecting trees, computing
          vegetation indices, and measuring forest change — using ISRO and global
          imagery with peer-reviewed deep learning models.
        </p>
        <div className="fade-up delay-3 flex flex-col sm:flex-row gap-4 justify-center">
          <a href={DEMO_URL} target="_blank" rel="noreferrer"
             className="px-8 py-3.5 bg-forest-700 text-white font-semibold rounded-xl hover:bg-forest-800 transition-colors shadow-lg shadow-forest-200">
            Launch Interactive Demo →
          </a>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer"
             className="px-8 py-3.5 border-2 border-gray-200 text-gray-700 font-semibold rounded-xl hover:border-forest-400 hover:text-forest-700 transition-colors">
            View on GitHub
          </a>
        </div>
      </div>
    </section>
  )
}

function StatsBar() {
  const stats = [
    { val: "0.25 m", label: "Finest resolution (Cartosat-3)" },
    { val: "13",     label: "Research models implemented" },
    { val: "1984",   label: "Historical data from (Landsat 5)" },
    { val: "Free",   label: "Core data sources" },
  ]
  return (
    <div className="bg-forest-800 text-white py-10 px-6">
      <div className="max-w-5xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-8 text-center">
        {stats.map(s => (
          <div key={s.val}>
            <div className="text-3xl font-extrabold text-forest-300">{s.val}</div>
            <div className="text-sm text-forest-100 mt-1">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Features() {
  return (
    <section id="features" className="py-24 px-6 bg-white">
      <div className="max-w-6xl mx-auto">
        <SectionHeader
          tag="Features"
          title="Everything needed for satellite tree analysis"
          sub="Built on peer-reviewed models from remote sensing and deep learning literature."
        />
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map(f => (
            <div key={f.title}
                 className="p-6 rounded-2xl border border-gray-100 hover:border-forest-200 hover:shadow-md transition-all">
              <div className="text-3xl mb-3">{f.icon}</div>
              <h3 className="font-bold text-gray-900 mb-2">{f.title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function Pipeline() {
  return (
    <section id="pipeline" className="py-24 px-6 bg-forest-50">
      <div className="max-w-4xl mx-auto">
        <SectionHeader
          tag="How it works"
          title="Six steps from satellite to tree count"
          sub="Run the full pipeline with one command or interactively via Jupyter notebooks."
        />
        <div className="space-y-4">
          {PIPELINE.map((s, i) => (
            <div key={s.step}
                 className="flex items-start gap-5 p-5 bg-white rounded-2xl border border-gray-100 shadow-sm">
              <span className="shrink-0 w-10 h-10 flex items-center justify-center rounded-full bg-forest-700 text-white font-bold text-sm">
                {s.step}
              </span>
              <div>
                <div className="font-semibold text-gray-900">{s.label}</div>
                <div className="text-sm text-gray-500 mt-0.5">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-8 p-5 bg-forest-900 text-forest-100 rounded-2xl font-mono text-sm">
          <span className="text-forest-400">$</span> python scripts/run_pipeline.py --config config.yaml --source gee
        </div>
      </div>
    </section>
  )
}

function DataSources() {
  return (
    <section id="data" className="py-24 px-6 bg-white">
      <div className="max-w-5xl mx-auto">
        <SectionHeader
          tag="Data sources"
          title="ISRO, ESA, and NASA imagery"
          sub="Step-by-step access guide for every data source included in the repository."
        />
        <div className="overflow-x-auto rounded-2xl border border-gray-100 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-forest-50 text-forest-800">
              <tr>
                {["Source", "Resolution", "Free?", "Best for"].map(h => (
                  <th key={h} className="text-left px-5 py-3 font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {SOURCES.map(s => (
                <tr key={s.name} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 font-medium text-gray-900">{s.name}</td>
                  <td className="px-5 py-3 font-mono text-forest-700">{s.res}</td>
                  <td className="px-5 py-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                      s.free
                        ? "bg-green-100 text-green-800"
                        : "bg-amber-100 text-amber-800"
                    }`}>
                      {s.free ? "Free" : "Paid/Approval"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-500">{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

function DemoEmbed() {
  return (
    <section className="py-24 px-6 bg-forest-50">
      <div className="max-w-5xl mx-auto text-center">
        <SectionHeader
          tag="Live demo"
          title="Try it now — no setup required"
          sub="Interactive demo running on Hugging Face Spaces. Adjust resolution, biome, and tree density with sliders."
        />
        <div className="rounded-2xl overflow-hidden border-2 border-forest-200 shadow-xl aspect-video bg-forest-900 flex items-center justify-center">
          {/* Replace src with your actual Hugging Face Spaces or Render URL */}
          <div className="text-center text-white">
            <div className="text-5xl mb-4">🌳</div>
            <p className="text-forest-200 font-medium mb-4">
              Deploy to Hugging Face Spaces and update <code className="bg-forest-800 px-2 py-0.5 rounded text-forest-300">DEMO_URL</code> in <code className="bg-forest-800 px-2 py-0.5 rounded text-forest-300">page.jsx</code>
            </p>
            <a href={DEMO_URL} target="_blank" rel="noreferrer"
               className="inline-block px-6 py-2.5 bg-forest-400 text-forest-900 font-semibold rounded-xl hover:bg-forest-300 transition-colors">
              Open Demo in New Tab →
            </a>
          </div>
        </div>
        <p className="mt-4 text-sm text-gray-400">
          Once deployed, replace the placeholder above with:{" "}
          <code className="bg-gray-100 px-2 py-0.5 rounded text-gray-700">&lt;iframe src=&quot;YOUR_SPACES_URL&quot; /&gt;</code>
        </p>
      </div>
    </section>
  )
}

function QuickStart() {
  const steps = [
    { cmd: "git clone https://github.com/abhisekparichha/milliontwigs", comment: "# clone the repo" },
    { cmd: "pip install -r requirements-demo.txt", comment: "# install dependencies" },
    { cmd: "streamlit run app.py", comment: "# launch the demo locally" },
  ]
  return (
    <section className="py-24 px-6 bg-white">
      <div className="max-w-3xl mx-auto text-center">
        <SectionHeader
          tag="Quick start"
          title="Running locally in 3 commands"
          sub="No account or API key needed for the demo. Real satellite data requires free registration."
        />
        <div className="text-left bg-gray-950 rounded-2xl p-6 space-y-3 font-mono text-sm shadow-xl">
          {steps.map((s, i) => (
            <div key={i} className="flex flex-wrap gap-x-3">
              <span className="text-forest-400">$</span>
              <span className="text-gray-100">{s.cmd}</span>
              <span className="text-gray-500">{s.comment}</span>
            </div>
          ))}
        </div>
        <a href={DOCS_URL} target="_blank" rel="noreferrer"
           className="inline-block mt-8 px-8 py-3 border-2 border-forest-600 text-forest-700 font-semibold rounded-xl hover:bg-forest-50 transition-colors">
          Read the full documentation →
        </a>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="py-12 px-6 bg-forest-900 text-forest-200 text-sm">
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
        <div>
          <span className="font-bold text-white">🌳 MillionTwigs</span>
          <span className="ml-3 text-forest-400">Open-source satellite vegetation analysis</span>
        </div>
        <div className="flex gap-6 text-forest-400">
          <a href={GITHUB_URL} target="_blank" rel="noreferrer" className="hover:text-white transition-colors">GitHub</a>
          <a href={DEMO_URL}   target="_blank" rel="noreferrer" className="hover:text-white transition-colors">Demo</a>
          <a href={DOCS_URL}   target="_blank" rel="noreferrer" className="hover:text-white transition-colors">Docs</a>
        </div>
      </div>
      <div className="max-w-5xl mx-auto mt-6 pt-6 border-t border-forest-800 text-forest-500 text-xs">
        Models: Tucker 1979 · Huete 2002 · Weinstein 2020 · Ronneberger 2015 · Kirillov 2023 · Jucker 2017 · Malila 1980
      </div>
    </footer>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────

function SectionHeader({ tag, title, sub }) {
  return (
    <div className="text-center mb-12">
      <span className="inline-block px-3 py-1 rounded-full bg-forest-100 text-forest-700 text-xs font-semibold uppercase tracking-wider mb-4">
        {tag}
      </span>
      <h2 className="text-3xl sm:text-4xl font-extrabold text-gray-900 mb-3">{title}</h2>
      {sub && <p className="text-gray-500 max-w-2xl mx-auto">{sub}</p>}
    </div>
  )
}

function GithubIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.44 9.8 8.2 11.38.6.11.82-.26.82-.58v-2.17c-3.34.73-4.04-1.61-4.04-1.61-.54-1.38-1.33-1.75-1.33-1.75-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.8 1.3 3.49 1 .11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 3-.4c1.02 0 2.04.14 3 .4 2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.81 5.63-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58C20.57 21.8 24 17.3 24 12c0-6.63-5.37-12-12-12z"/>
    </svg>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function Page() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <StatsBar />
        <Features />
        <Pipeline />
        <DataSources />
        <DemoEmbed />
        <QuickStart />
      </main>
      <Footer />
    </>
  )
}
