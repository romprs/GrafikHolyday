import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createLeaveRequest } from "../api/leaveRequests";
import { ApiError } from "../api/client";

export function RequestFormPage() {
  const queryClient = useQueryClient();
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const days =
    dateFrom && dateTo
      ? Math.floor(
          (new Date(dateTo).getTime() - new Date(dateFrom).getTime()) / 86_400_000,
        ) + 1
      : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);
    setSubmitting(true);
    try {
      await createLeaveRequest({ date_from: dateFrom, date_to: dateTo, comment });
      setSuccess(true);
      setDateFrom("");
      setDateTo("");
      setComment("");
      queryClient.invalidateQueries({ queryKey: ["my-leave-requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-balance"] });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось отправить заявку");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <h3>Новая заявка на отпуск</h3>
      <label>
        Дата начала
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
          required
          style={{ display: "block" }}
        />
      </label>
      <label>
        Дата окончания
        <input
          type="date"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
          required
          style={{ display: "block" }}
        />
      </label>
      {days !== null && <p>Длительность: {days} дн.</p>}
      <label>
        Комментарий
        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      <button type="submit" disabled={submitting}>
        Отправить
      </button>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {success && <p style={{ color: "green" }}>Заявка отправлена на согласование.</p>}
    </form>
  );
}
