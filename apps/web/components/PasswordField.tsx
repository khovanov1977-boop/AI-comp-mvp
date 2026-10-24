"use client";

import { useState } from "react";

type PasswordFieldProps = {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  placeholder: string;
  minLength?: number;
  maxLength?: number;
};

export function PasswordField({ id, value, onChange, autoComplete, placeholder, minLength, maxLength }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return <div className="field">
    <label className="label" htmlFor={id}>Пароль</label>
    <div className="password-control">
      <input
        id={id}
        className="input"
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        minLength={minLength}
        maxLength={maxLength}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
      <button
        className="password-toggle"
        type="button"
        aria-label={visible ? "Скрыть пароль" : "Показать пароль"}
        aria-pressed={visible}
        onClick={() => setVisible(!visible)}
      >{visible ? "Скрыть" : "Показать"}</button>
    </div>
  </div>;
}
