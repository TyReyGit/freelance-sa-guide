import ChatCard from "@/components/ChatCard";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 px-4 py-16 dark:bg-black sm:py-24">
      <div className="mb-8 max-w-xl text-center">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
          FreelanceSA Guide
        </h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
          Ask questions about tax as a freelancer in South Africa. Answers are
          grounded in official SARS guides with page citations — and the tool
          will tell you honestly when something isn&apos;t covered in the
          source documents, rather than guessing.
        </p>
      </div>

      <ChatCard />

      <footer className="mt-16 max-w-xl text-center text-xs text-zinc-500 dark:text-zinc-500">
        <p>
          Built by Tyrone Naidoo — control systems engineer building AI
          systems.{" "}
          <a
            href="https://github.com/TyReyGit"
            className="underline hover:text-zinc-700 dark:hover:text-zinc-300"
          >
            GitHub
          </a>{" "}
          ·{" "}
          <a
            href="https://www.linkedin.com/in/tyrone-naidoo-solutionist"
            className="underline hover:text-zinc-700 dark:hover:text-zinc-300"
          >
            LinkedIn
          </a>
        </p>
        <p className="mt-2">
          Sourced from official SARS guides. Not affiliated with or endorsed
          by SARS. Educational tool only — not tax advice. Verify anything
          important with SARS or a registered tax practitioner.
        </p>
      </footer>
    </div>
  );
}