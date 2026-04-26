import React, { useState, useRef } from "react";
import { Image, PenLine, X } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useLanguage } from "../../i18n/LanguageContext";
import {
  canUserPost, getUserPostCountToday, getDailyLimit,
  incrementPostCount, loadPosts, savePosts, toSlug, type BlogPost,
} from "../blogStore";

const CATEGORY_KEYS = [
  { key: "technology", value: "Teknoloji" },
  { key: "ai", value: "Yapay Zeka" },
  { key: "design", value: "Tasarım" },
  { key: "data_science", value: "Veri Bilimi" },
  { key: "security", value: "Güvenlik" },
  { key: "cloud", value: "Cloud" },
  { key: "career", value: "Kariyer" },
];

export default function CreatePostModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (post: BlogPost) => void;
}) {
  const { user, plan, role } = useAuth();
  const { t } = useLanguage();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("Teknoloji");
  const [tags, setTags] = useState("");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!open) return null;

  const email = (user as any)?.email || "";
  const userName =
    (user as any)?.user_metadata?.full_name ||
    email.split("@")[0] ||
    t("blog.anonymous");
  const todayCount = getUserPostCountToday(email);
  const limit = getDailyLimit(plan, role);
  const canPost = canUserPost(email, plan, role);

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim() || !canPost) return;

    const newPost: BlogPost = {
      id: `post-${Date.now()}`,
      title: title.trim(),
      content: content.trim(),
      summary: content.trim().slice(0, 200) + (content.length > 200 ? "..." : ""),
      category,
      slug: toSlug(title) + "-" + Date.now(),
      image: imagePreview || `https://picsum.photos/id/${Math.floor(Math.random() * 200)}/900/400`,
      author: { name: userName, email, role: role || "user", plan: plan || "free" },
      tags: tags.split(",").map(tag => tag.trim()).filter(Boolean),
      createdAt: new Date().toISOString(),
      views: 0,
      likes: [],
      comments: [],
    };

    const posts = loadPosts();
    posts.unshift(newPost);
    savePosts(posts);
    incrementPostCount(email);
    onCreated(newPost);

    setTitle("");
    setContent("");
    setCategory("Teknoloji");
    setTags("");
    setImagePreview(null);
    onClose();
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

            <div className="blog-modal-form-field">
              <label>{t("blog.label_image")}</label>
              <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="blog-img-upload-btn"
                >
                  <Image size={15} />
                  {t("blog.select_image")}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  style={{ display: "none" }}
                />
                {imagePreview && (
                  <img
                    src={imagePreview}
                    alt="Preview"
                    style={{ height: 56, width: 84, objectFit: "cover", borderRadius: "8px", border: "1px solid var(--color-border)" }}
                  />
                )}
              </div>
            </div>

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
                disabled={!canPost || !title.trim() || !content.trim()}
                className="btn-primary"
                style={{ flex: 1 }}
              >
                {t("blog.publish")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
