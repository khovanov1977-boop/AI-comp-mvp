"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../../components/AuthProvider";
import { PasswordField } from "../../components/PasswordField";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (!loading && user) router.replace("/characters"); }, [loading, user, router]);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await login(email, password); router.replace("/characters"); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Не удалось войти."); }
    finally { setBusy(false); }
  }
  return <main className="auth-page"><div className="auth-intro"><span className="eyebrow">С ВОЗВРАЩЕНИЕМ</span><h1>Продолжим <em>разговор?</em></h1><p>Войдите, чтобы вернуться к своим персонажам, перепискам и сохранённым моментам.</p></div><form className="auth-card" onSubmit={submit}><h2>Войти в аккаунт</h2><label className="field"><span className="label">Электронная почта</span><input className="input" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@example.com" /></label><PasswordField id="login-password" value={password} onChange={setPassword} autoComplete="current-password" placeholder="Введите пароль" />{error && <p className="form-error" role="alert">{error}</p>}<button className="button" disabled={busy} type="submit">{busy ? "Входим…" : "Войти"} <span>→</span></button><p className="auth-switch">Нет аккаунта? <Link href="/register">Зарегистрироваться</Link></p></form></main>;
}
