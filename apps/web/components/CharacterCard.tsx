"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Character } from "@ai-companion/shared";
import { getApiAssetUrl, getAppearance } from "../lib/api";

export function CharacterCard({ character }: { character: Character }) {
  const [portraitUrl, setPortraitUrl] = useState("");
  const relationshipLabel = character.relationship_mode === "romantic" ? "БЛИЗКИЕ ОТНОШЕНИЯ"
    : character.relationship_mode === "friend" ? (character.gender === "female" ? "ПОДРУГА" : character.gender === "male" ? "ДРУГ" : "ДРУЖЕСКОЕ ОБЩЕНИЕ")
    : character.relationship_mode === "colleague" ? "КОЛЛЕГА"
    : character.relationship_mode === "relative" ? "РОДСТВЕННИК" : "СОБЕСЕДНИК";

  useEffect(() => {
    let active = true;
    getAppearance(character.id).then((appearance) => {
      const references = appearance.published?.references;
      const url = references?.clothing?.url ?? references?.body?.url ?? references?.face?.url ?? "";
      if (active) setPortraitUrl(url);
    }).catch(() => undefined);
    return () => { active = false; };
  }, [character.id]);

  return (
    <article className="card character-card">
      <div className="character-card-art">{portraitUrl ? <img src={getApiAssetUrl(portraitUrl)} alt={`Образ персонажа ${character.name}`} /> : <><span>{character.name.slice(0, 1).toUpperCase()}</span><span className="character-card-orbit" /></>}</div>
      <div className="character-card-content"><span className="character-card-type">{relationshipLabel}</span><div className="card-title">{character.name}</div>
      <p>{character.personality_description || "Новая история ждёт первого разговора."}</p>
      <Link className="character-card-link" href={`/chat/${character.id}`}>Открыть диалог <span>↗</span></Link></div>
    </article>
  );
}
