"use client";

import { useState } from "react";

const API_URL = "http://localhost:8000/ask";

type Provider = "gemini" | "groq";

type Source = {
  source: string;
  page: number;
};

type AskResponse = {
  answer: string;
  sources: Source[];
};

export default function ChatCard() {
  const [question, setQuestion] = useState("");
  const [provider, setProvider] = useState<Provider>("groq");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, provider }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(
          body?.detail || `Request failed with status ${res.status}`
        );
      }

      const data: AskResponse = await res.json();
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
        Freelance SA Guide
      </h1>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        Ask a question and get an answer grounded in the source documents.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question…"
          rows={3}
          className="w-full resize-none rounded-lg border border-zinc-300 bg-white px-4 py-3 text-base text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
        />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1 rounded-lg border border-zinc-300 p-1 dark:border-zinc-700">
            {(["groq", "gemini"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setProvider(p)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
                  provider === p
                    ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="rounded-lg bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            {loading ? "Asking…" : "Ask"}
          </button>
        </div>
      </form>

      <div className="mt-8">
        {loading && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Thinking…
          </p>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-400">
            {error}
          </div>
        )}

        {result && (
          <div className="flex flex-col gap-4">
            <p className="whitespace-pre-wrap text-base leading-relaxed text-zinc-800 dark:text-zinc-200">
              {result.answer}
            </p>

            {result.sources.length > 0 && (
              <div className="border-t border-zinc-200 pt-3 dark:border-zinc-800">
                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
                  Sources
                </p>
                <ul className="flex flex-col gap-1">
                  {result.sources.map((s, i) => (
                    <li
                      key={i}
                      className="text-sm text-zinc-500 dark:text-zinc-400"
                    >
                      {s.source} — p.{s.page}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
