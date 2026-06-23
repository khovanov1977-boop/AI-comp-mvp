"use client";

import { useEffect, useState } from "react";
import type { Character } from "@ai-companion/shared";
import { CharacterCard } from "../../components/CharacterCard";
import { CharacterCreateForm } from "../../components/CharacterCreateForm";
import { listCharacters } from "../../lib/api";

export default function CharactersPage() {
  const [characters, setCharacters] = useState<Character[]>([]);
  const [error, setError] = useState("");

  async function refresh() {
    setError("");
    try {
      setCharacters(await listCharacters());
    } catch {
      setError("Could not load characters. Start the backend first.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <main className="shell">
      <div className="topbar">
        <div>
          <div className="brand">Characters</div>
          <p className="muted">Create a companion, then open chat.</p>
        </div>
      </div>

      <div className="grid">
        <CharacterCreateForm onCreated={refresh} />
        <section className="stack">
          {error ? <p className="muted">{error}</p> : null}
          <div className="cards">
            {characters.map((character) => (
              <CharacterCard key={character.id} character={character} />
            ))}
          </div>
          {characters.length === 0 ? <p className="muted">No characters yet.</p> : null}
        </section>
      </div>
    </main>
  );
}
