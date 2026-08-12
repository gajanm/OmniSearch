"use client";

import { useState } from "react";

type SearchResult = {
  id: string;
  score: number;
  title: string;
  description: string;
  category: string;
  price: number;
};

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const handleSearch = async () => {
    if (!query.trim()) {
      setError("Enter a search query.");
      return;
    }
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${backendUrl}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, top_k: topK })
      });
      if (!response.ok) {
        throw new Error("Search failed. Check your backend logs.");
      }
      const data = await response.json();
      setResults(data.results ?? []);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Search failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-12">
      <header className="space-y-3">
        <p className="text-sm uppercase tracking-[0.2em] text-slate-400">
          OmniSearch
        </p>
        <h1 className="text-4xl font-semibold text-white">
          Semantic product search
        </h1>
        <p className="text-slate-300">
          Ask for products in natural language. Results are ranked by semantic
          similarity from Pinecone.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-lg">
        <div className="flex flex-col gap-4 md:flex-row md:items-end">
          <div className="flex-1">
            <label className="text-sm font-medium text-slate-300" htmlFor="query">
              Search query
            </label>
            <input
              id="query"
              className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 focus:border-indigo-400 focus:outline-none"
              placeholder="e.g. lightweight backpack for weekend hikes"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-300" htmlFor="topK">
              Top K
            </label>
            <select
              id="topK"
              className="mt-2 w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-slate-100 focus:border-indigo-400 focus:outline-none"
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            >
              {[3, 5, 10, 20].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <button
            className="rounded-lg bg-indigo-500 px-6 py-3 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:bg-indigo-800"
            onClick={handleSearch}
            disabled={loading}
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
        {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Results</h2>
        {results.length === 0 && !loading ? (
          <p className="text-slate-400">
            No results yet. Try searching for something like "wireless earbuds".
          </p>
        ) : (
          <div className="space-y-4">
            {results.map((result) => (
              <article
                key={result.id}
                className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-xl font-semibold text-white">
                    {result.title}
                  </h3>
                  <span className="rounded-full bg-indigo-500/20 px-3 py-1 text-xs font-semibold text-indigo-200">
                    {result.score.toFixed(3)}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-300">
                  {result.description}
                </p>
                <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-400">
                  <span className="rounded-full bg-slate-800 px-3 py-1">
                    {result.category}
                  </span>
                  <span className="rounded-full bg-slate-800 px-3 py-1">
                    ${result.price.toFixed(2)}
                  </span>
                  <span className="rounded-full bg-slate-800 px-3 py-1">
                    ID: {result.id}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
