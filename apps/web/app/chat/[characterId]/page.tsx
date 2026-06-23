import Link from "next/link";
import { ChatWindow } from "../../../components/ChatWindow";
import { MediaPanel } from "../../../components/MediaPanel";
import { getCharacter } from "../../../lib/api";

export default async function ChatPage({ params }: { params: Promise<{ characterId: string }> }) {
  const { characterId } = await params;
  const character = await getCharacter(characterId);

  return (
    <main className="shell">
      <div className="topbar">
        <div>
          <div className="brand">{character.name}</div>
          <p className="muted">
            {character.relationship_mode} · {character.communication_style || "mock companion"}
          </p>
        </div>
        <nav className="nav">
          <Link href="/characters">Characters</Link>
        </nav>
      </div>

      <div className="chat-layout">
        <ChatWindow characterId={characterId} />
        <MediaPanel />
      </div>
    </main>
  );
}
