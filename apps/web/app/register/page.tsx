"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../../components/AuthProvider";
import { PasswordField } from "../../components/PasswordField";

export default function RegisterPage() {
  const { register, user, loading } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!loading && user) router.replace("/characters"); }, [loading, user, router]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await register(email, password, name); router.replace("/characters"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось создать аккаунт."); }
    finally { setBusy(false); }
  }
  return <main className="auth-page"><div className="auth-intro"><span className="eyebrow">НАЧАЛО ВАШЕЙ ИСТОРИИ</span><h1>Место для <em>ваших диалогов.</em></h1><p>Один аккаунт хранит ваших персонажей, переписки и созданные медиа. Возвращайтесь к ним в любой момент.</p><div className="auth-accent">✳ <span>Личное пространство для каждого</span></div></div><form className="auth-card" onSubmit={submit}><h2>Создать аккаунт</h2><label className="field"><span className="label">Как к вам обращаться</span><input className="input" autoComplete="name" maxLength={100} required value={name} onChange={(event) => setName(event.target.value)} placeholder="Ваше имя" /></label><label className="field"><span className="label">Электронная почта</span><input className="input" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" /></label><PasswordField id="register-password" value={password} onChange={setPassword} autoComplete="new-password" minLength={10} maxLength={128} placeholder="Не менее 10 символов" />{error && <p className="form-error" role="alert">{error}</p>}<button className="button" disabled={busy} type="submit">{busy ? "Создаём аккаунт…" : "Создать аккаунт"} <span>→</span></button><p className="auth-switch">Уже зарегистрированы? <Link href="/login">Войти</Link></p></form></main>;
}
