import Link from "next/link";
import type { Character } from "@ai-companion/shared";

export function CharacterCard({ character }: { character: Character }) {
  return (
    <article className="card">
      <div className="card-title">{character.name}</div>
      <div className="muted">{character.relationship_mode}</div>
      <p>{character.personality_description || "A new companion waiting for a first conversation."}</p>
      <Link className="button" href={`/chat/${character.id}`}>
        Open chat
      </Link>
    </article>
  );
}
