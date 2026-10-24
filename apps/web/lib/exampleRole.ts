import type { ExampleCharacter } from "./api";

export function exampleRoleName(item: ExampleCharacter) {
  if (item.relationship_mode === "friend") return item.gender === "female" ? "Подруга" : item.gender === "male" ? "Друг" : "Дружеское общение";
  if (item.relationship_mode === "companion") return item.gender === "female" ? "Собеседница" : "Собеседник";
  if (item.relationship_mode === "colleague") return "Коллега";
  if (item.relationship_mode === "relative") return "Родственник";
  return "Романтический персонаж";
}
