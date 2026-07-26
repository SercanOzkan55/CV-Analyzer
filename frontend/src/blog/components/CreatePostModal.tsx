import React, { useState } from "react";
import { Loader2, PenLine, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import { createBlogPost } from "../../api";
import { getDailyLimit, type BlogPost } from "../blogStore";

const CATEGORY_KEYS = [
  { key: "technology", value: "Technology" },
  { key: "ai", value: "Artificial Intelligence" },
  { key: "design", value: "Design" },
  { key: "data_science", value: "Data Science" },
  { key: "security", value: "Security" },
  { key: "cloud", value: "Cloud" },
  { key: "career", value: "Career" },
];

export default function CreatePostModal({
  open,
  onClose,
  onCreated,
  token,
  todayCount,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (post: BlogPost, used: number) => void;
  token: string | null;
  todayCount: number;
}) {
  const { plan, role } = useAuth();
  const { t } = useLanguage();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("Technology");
  const [tags, setTags] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  const limit = getDailyLimit(plan, role);
  const canPost = Boolean(token) && todayCount < limit;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim() || !canPost || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const result = await createBlogPost(token, {
        title: title.trim(),
        content: content.trim(),
        category,
        tags: tags.split(",").map(tag => tag.trim()).filter(Boolean).slice(0, 5),
      });
      onCreated(result.post as BlogPost, Number(result?.quota?.used || todayCount + 1));
      setTitle("");
      setContent("");
      setCategory("Technology");
      setTags("");
      onClose();
    } catch (err: any) {
      setError(err?.status === 422 ? t("blog.moderation_rejected") : (err?.message || t("blog.publish_failed")));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={t("blog.create_post_title")}
    >
      <div
        className="modal-content"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: 600 }}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <PenLine size={18} style={{ color: "var(--color-accent)" }} />
            <h3>{t("blog.create_post_title")}</h3>
          </div>
          <button
            onClick={onClose}
            className="modal-close"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Quota indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "0.82rem",
              marginBottom: "6px",
            }}
          >
            <span style={{ color: "var(--color-text-secondary)" }}>
              {t("blog.today_quota")}{" "}
              <span style={{ color: canPost ? "var(--color-accent)" : "var(--color-danger)", fontWeight: 700 }}>
                {todayCount}/{limit}
              </span>
            </span>
            {!canPost && (
              <span style={{ color: "var(--color-danger)", fontSize: "0.75rem" }}>
                {t("blog.daily_limit_reached")}
              </span>
            )}
          </div>
          <div className="blog-modal-quota-bar-track">
            <div
              className="blog-modal-quota-bar-fill"
              style={{
                width: `${Math.min(100, (todayCount / limit) * 100)}%`,
                background: canPost ? "var(--gradient-accent)" : "var(--color-danger)",
              }}
            />
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ marginTop: "20px" }}>
            <div className="blog-modal-form-field">
              <label>{t("blog.label_title")}</label>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder={t("blog.placeholder_title")}
                className="blog-modal-input"
                required
              />
            </div>

            <div className="blog-modal-form-field">
              <label>{t("blog.label_category")}</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                className="blog-modal-select"
              >
                {CATEGORY_KEYS.map(c => (
                  <option key={c.value} value={c.value}>
                    {t(`blog.category_${c.key}`)}
                  </option>
                ))}
              </select>
            </div>

            <div className="blog-modal-form-field">
              <label>{t("blog.label_content")}</label>
              <textarea
                value={content}
                onChange={e => setContent(e.target.value)}
                placeholder={t("blog.placeholder_content")}
                rows={7}
                className="blog-modal-textarea"
                required
              />
            </div>

            <div className="blog-modal-form-field">
              <label>
                {t("blog.label_tags")}{" "}
                <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>
                  ({t("blog.tags_hint")})
                </span>
              </label>
              <input
                value={tags}
                onChange={e => setTags(e.target.value)}
                placeholder={t("blog.placeholder_tags")}
                className="blog-modal-input"
              />
            </div>

            <p className="blog-comment-hint">{t("blog.moderation_notice")}</p>
            {error && <p role="alert" style={{ color: "var(--color-danger)", fontSize: "0.85rem" }}>{error}</p>}

            <div style={{ display: "flex", gap: "12px", marginTop: "8px" }}>
              <button
                type="button"
                onClick={onClose}
                className="btn-outline"
                style={{ flex: 1 }}
              >
                {t("blog.cancel")}
              </button>
              <button
                type="submit"
                disabled={!canPost || !title.trim() || content.trim().length < 40 || submitting}
                className="btn-primary"
                style={{ flex: 1 }}
              >
                {submitting && <Loader2 size={14} className="animate-spin" />}
                {submitting ? t("blog.publishing") : t("blog.publish")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
