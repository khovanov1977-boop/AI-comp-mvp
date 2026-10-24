"use client";

import Link from "next/link";
import { useAuth } from "../components/AuthProvider";
import { ExampleCatalog } from "../components/ExampleCatalog";

export default function HomePage() {
  const { user } = useAuth();
  return <main className="landing">
    <section className="landing-hero">
      <div className="hero-copy">
        <span className="eyebrow"><span className="eyebrow-line" /> ВАШЕ ЛИЧНОЕ ПРОСТРАНСТВО</span>
        <h1>Общение, к которому <em>хочется возвращаться.</em></h1>
        <p>Создайте персонажа с собственным характером. Общайтесь или разыгрывайте роли, продолжайте с того места, где остановились, и сохраняйте важные моменты — в словах, голосе, фото и видео.</p>
        <div className="hero-actions">
          <Link className="button hero-button" href={user ? "/characters" : "/register"}>{user ? "Открыть моё пространство" : "Начать общение"}<span aria-hidden="true">↗</span></Link>
          {!user && <Link className="quiet-link" href="/login">У меня уже есть аккаунт <span>→</span></Link>}
        </div>
        <div className="hero-footnote"><span className="sparkle">✳</span> Ваши персонажи и переписки доступны только вам</div>
      </div>
      <div className="hero-art"><img src="/hero-companions.webp" alt="Четверо собеседников — женщины и мужчины — общаются друг с другом" /><span className="art-caption">У каждого своя история</span></div>
    </section>
    <ExampleCatalog embedded />
    <section className="landing-join">
      <div><span className="eyebrow">ВАШЕ ПРОДОЛЖЕНИЕ</span><h2>Выберите персонажа или создайте собственного и начните свою историю</h2></div>
      <Link className="button" href={user ? "/characters" : "/register"}>{user ? "Открыть моих персонажей" : "Присоединиться"} <span aria-hidden="true">↗</span></Link>
    </section>
  </main>;
}
