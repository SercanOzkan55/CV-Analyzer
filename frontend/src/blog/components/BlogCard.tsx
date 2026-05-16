import React from "react";
import { Calendar, Clock, Eye, Globe, Loader2, MessageCircle, ThumbsUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { formatDate, readingTime, getAvatarColor, getInitials, type BlogPost } from "../blogStore";
import { useTranslation } from "../useTranslation";
import { useLanguage } from "../../i18n/LanguageContext";
import { LANG_LABELS } from "../translateService";

const CATEGORY_GRADIENTS: Record<string, string> = {
  Teknoloji: "linear-gradient(135deg, #3b82f6, #6366f1)",
  "Yapay Zeka": "linear-gradient(135deg, #10b981, #06b6d4)",
  Tasarım: "linear-gradient(135deg, #a855f7, #c084fc)",
  "Veri Bilimi": "linear-gradient(135deg, #f59e0b, #f97316)",
  Güvenlik: "linear-gradient(135deg, #ef4444, #f43f5e)",
  Cloud: "linear-gradient(135deg, #0ea5e9, #38bdf8)",
  Kariyer: "linear-gradient(135deg, #c084fc, #f472b6)",
};

export default function BlogCard({ post }: { post: BlogPost }) {
  const navigate = useNavigate();
  const { lang, t } = useLanguage();
  const { isTranslated, isLoading, translated, targetLang, toggle } = useTranslation(
    lang,
    t("blog.translation_failed")
  );

  const roleLabel =
    post.author.role === "recruiter"
      ? t("blog.role_recruiter")
      : post.author.plan === "premium"
      ? t("blog.role_premium")
      : t("blog.role_member");

  const displayTitle = isTranslated && translated ? translated.title : post.title;
  const displaySummary = isTranslated && translated ? translated.summary : post.summary;
  const catGradient = CATEGORY_GRADIENTS[post.category] || "var(--gradient-accent)";

  return (
    <article
      className="blog-card"
      onClick={() => navigate(`/blog/${post.slug}`)}
      role="link"
      tabIndex={0}
      onKeyDown={e => e.key === "Enter" && navigate(`/blog/${post.slug}`)}
    >
      {/* Image */}
      <div className="blog-card-img-wrap">
        <img src={post.image} alt={post.title} className="blog-card-img" />
        <div className="blog-card-img-overlay" />

        {/* Badges overlay */}
        <div className="blog-card-badges">
          <span className="blog-cat-badge" style={{ background: catGradient }}>
            {post.category}
          </span>
          <button
            className={`blog-translate-btn${isTranslated ? " active" : ""}`}
            onClick={e => { e.stopPropagation(); toggle(post); }}
            title={
              isTranslated
                ? t("blog.show_original")
                : t("blog.translate_to").replace("{lang}", LANG_LABELS[targetLang] || targetLang)
            }
          >
            {isLoading ? <Loader2 size={11} className="animate-spin" /> : <Globe size={11} />}
            <span>{isTranslated ? t("blog.original") : t("blog.translate")}</span>
          </button>
        </div>

        {/* Stats overlay */}
        <div className="blog-card-stats">
          <span className="blog-card-stat"><Eye size={12} /> {post.views}</span>
          <span className="blog-card-stat"><ThumbsUp size={12} /> {post.likes.length}</span>
          <span className="blog-card-stat"><MessageCircle size={12} /> {post.comments.length}</span>
        </div>
      </div>

      {/* Body */}
      <div className="blog-card-body">
        <h3 className="blog-card-title">{displayTitle}</h3>
        <p className="blog-card-summary">{displaySummary}</p>

        {/* Tags */}
        {post.tags.length > 0 && (
          <div className="blog-card-tags">
            {post.tags.slice(0, 3).map((tag, i) => (
              <span key={i} className="blog-tag-chip">#{tag}</span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="blog-card-footer">
          <div className="blog-card-author">
            <div
              className="blog-author-avatar"
              style={{ background: getAvatarColor(post.author.name) }}
            >
              {getInitials(post.author.name)}
            </div>
            <div>
              <div className="blog-author-name">{post.author.name}</div>
              <div className="blog-author-role">{roleLabel}</div>
            </div>
          </div>
          <div className="blog-card-meta">
            <span className="blog-card-meta-item">
              <Calendar size={11} />
              {formatDate(post.createdAt, t("blog.months"))}
            </span>
            <span className="blog-card-meta-item">
              <Clock size={11} />
              {readingTime(post.content, t("blog.reading_time"))}
            </span>
          </div>
        </div>
      </div>
    </article>
  );
}
