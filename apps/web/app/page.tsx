"use client";

import Link from "next/link";
import { useAuth } from "../components/AuthProvider";

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
      <div className="hero-art" aria-hidden="true"><div className="hero-art-glow" /><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="hero-core"><span>AI</span></div><span className="art-caption">место, где начинается история</span></div>
    </section>
    <section className="landing-features">
      <div><span className="feature-index">01 / ХАРАКТЕР</span><h2>Создайте того, с кем интересно</h2><p>Настройте личность, манеру общения и внешний вид персонажа.</p></div>
      <div><span className="feature-index">02 / ДИАЛОГ</span><h2>Персонажи, которые помнят разговор</h2><p>Переписка, голосовые сообщения и ролевые игры с памятью о ваших совместных историях.</p></div>
      <div><span className="feature-index">03 / МОМЕНТЫ</span><h2>Истории становятся видимыми</h2><p>Создавайте фотографии и короткие видео в рамках ваших сцен.</p></div>
    </section>
  </main>;
}
