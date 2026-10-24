"use client";

import { useEffect, useState } from "react";
import { RequireAuth } from "../../components/AppChrome";
import { useAuth } from "../../components/AuthProvider";
import { getAccountLimits, type AccountLimits } from "../../lib/api";

const quotas: { key: keyof AccountLimits; label: string; icon: string }[] = [
  { key: "images_count", label: "Фотографии", icon: "◈" },
  { key: "videos_count", label: "Видео", icon: "▷" },
  { key: "text_messages_count", label: "Текстовые ответы", icon: "✳" },
  { key: "voice_messages_count", label: "Голосовые ответы", icon: "♫" },
];

export default function AccountPage() {
  const { user } = useAuth();
  const [limits, setLimits] = useState<AccountLimits | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (user) getAccountLimits().then(setLimits).catch((cause) => setError(cause instanceof Error ? cause.message : "Не удалось получить лимиты.")); }, [user]);
  return <RequireAuth><main className="shell account-page"><div className="dashboard-heading"><div><span className="eyebrow">ЛИЧНЫЙ КАБИНЕТ</span><h1>Ваш <em>аккаунт</em></h1><p>Данные профиля и доступные возможности тестирования.</p></div></div><div className="account-layout"><section className="account-profile"><div className="profile-avatar">{user?.display_name.slice(0, 1).toUpperCase()}</div><span className="eyebrow">ПРОФИЛЬ</span><h2>{user?.display_name}</h2><p>{user?.email}</p></section><section className="account-quotas"><span className="eyebrow">ЛИМИТЫ ТЕСТИРОВАНИЯ</span><h2>Доступно вам</h2><p>Лимиты действуют на весь аккаунт. Использованные генерации сохраняются в счётчике, даже если удалить персонажа.</p>{error && <p className="form-error" role="alert">{error}</p>}<div className="quota-list">{quotas.map(({ key, label, icon }) => { const quota = limits?.[key]; const remaining = quota ? Math.max(0, quota.limit - quota.used) : null; return <div className="quota-item" key={key}><div className="quota-icon">{icon}</div><div className="quota-copy"><strong>{label}</strong><span>{quota ? `${quota.used} из ${quota.limit} использовано` : "Загрузка…"}</span><div className="quota-track"><span style={{ width: quota ? `${Math.min(100, quota.used / quota.limit * 100)}%` : "0%" }} /></div></div><b>{remaining ?? "—"}</b></div>; })}</div></section></div></main></RequireAuth>;
}
