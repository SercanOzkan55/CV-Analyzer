import React, { useState, useEffect } from "react";
import {
  ArrowLeft, Eye, Globe, Loader2, MessageCircle, ThumbsUp, Calendar, Clock,
} from "lucide-react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import CommentBox from "./components/CommentBox";
import CommentList from "./components/CommentList";
import BlogSidebar from "./components/BlogSidebar";
import { createBlogComment, fetchBlogPost, toggleBlogReaction } from "../api";
import { useTranslation } from "./useTranslation";
import { LANG_LABELS } from "./translateService";
import {
  formatDate, readingTime,
  getAvatarColor, getInitials, type BlogPost,
} from "./blogStore";
import "../pages/BlogPage.css";

const CATEGORY_GRADIENTS: Record<string, string> = {
  Technology: "linear-gradient(135deg, #3b82f6, #6366f1)",
  "Artificial Intelligence": "linear-gradient(135deg, #10b981, #06b6d4)",
  Design: "linear-gradient(135deg, #a855f7, #c084fc)",
  "Data Science": "linear-gradient(135deg, #f59e0b, #f97316)",
  Security: "linear-gradient(135deg, #ef4444, #f43f5e)",
  Cloud: "linear-gradient(135deg, #0ea5e9, #38bdf8)",
  Career: "linear-gradient(135deg, #c084fc, #f472b6)",
};

const CATEGORY_TRANSLATION_KEYS: Record<string, string> = {
  Technology: "technology",
  "Artificial Intelligence": "ai",
  Design: "design",
  "Data Science": "data_science",
  Security: "security",
  Cloud: "cloud",
  Career: "career",
};

export default function BlogDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const { lang, t } = useLanguage();
  const {
    isTranslated, isLoading, error: translateError, translated, targetLang, toggle,
  } = useTranslation(lang, t("blog.translation_failed"));
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState("");
  const [postLiked, setPostLiked] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchBlogPost(slug)
      .then(data => active && setPost(data?.post || null))
      .catch(() => active && setPost(null))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [slug]);

  async function handleAddComment(text: string) {
    if (!post || !token) return false;
    setActionError("");
    try {
      const data = await createBlogComment(token, post.id, { text });
      setPost(data.post);
      return true;
    } catch (err: any) {
      setActionError(err?.status === 422 ? t("blog.moderation_rejected") : (err?.message || t("blog.comment_failed")));
      return false;
    }
  }

  async function handleReply(commentId: string, text: string) {
    if (!post || !token) return false;
    setActionError("");
    try {
      const data = await createBlogComment(token, post.id, { text, parent_id: Number(commentId) });
      setPost(data.post);
      return true;
    } catch (err: any) {
      setActionError(err?.status === 422 ? t("blog.moderation_rejected") : (err?.message || t("blog.comment_failed")));
      return false;
    }
  }

  async function handleLikeComment(commentId: string) {
    if (!post || !token) return;
    try {
      const data = await toggleBlogReaction(token, "comment", commentId);
      setPost({
        ...post,
        comments: post.comments.map(comment =>
          comment.id === commentId
            ? { ...comment, likes: Array.from({ length: data.count }, (_, index) => `reaction-${index}`) }
            : comment
        ),
      });
    } catch { setActionError(t("blog.action_failed")); }
  }

  async function handleLikePost() {
    if (!post || !token) return;
    try {
      const data = await toggleBlogReaction(token, "post", post.id);
      setPostLiked(Boolean(data.liked));
      setPost({ ...post, likes: Array.from({ length: data.count }, (_, index) => `reaction-${index}`) });
    } catch { setActionError(t("blog.action_failed")); }
  }

  /* ── Not found ──────────────────────────────────── */
  if (loading || !post) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-primary)",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "3.5rem", marginBottom: "16px", opacity: 0.5 }}>{loading ? <Loader2 className="animate-spin" /> : "📄"}</div>
          <p style={{ color: "var(--color-text-muted)", marginBottom: "16px" }}>
            {loading ? t("common.loading") : t("blog.post_not_found")}
          </p>
          <button className="blog-detail-back" onClick={() => navigate("/blog")}>
            <ArrowLeft size={16} />
            {t("blog.back_to_blog")}
          </button>
        </div>
      </div>
    );
  }

  const catGradient = CATEGORY_GRADIENTS[post.category] || "var(--gradient-accent)";
  const isLiked = postLiked;

  return (
    <div style={{ background: "var(--bg-primary)", color: "var(--color-text)", minHeight: "100vh" }}>
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{ maxWidth: "1280px", margin: "0 auto", padding: "36px 24px 60px" }}
      >
        {/* Back link */}
        <button className="blog-detail-back" onClick={() => navigate("/blog")}>
          <ArrowLeft size={18} />
          {t("blog.back_to_all_posts")}
        </button>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
          {/* ── Article ─────────────────────────────── */}
          <div className="space-y-6 min-w-0">
            <motion.article
              className="blog-article"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.1 }}
            >
              {/* Cover image */}
              <div className="blog-article-img-wrap" style={{ background: catGradient }}>
                <div className="blog-article-img-overlay" />
                {/* Category badge over image */}
                <span
                  style={{
                    position: "absolute",
                    top: 20,
                    left: 20,
                    padding: "5px 14px",
                    borderRadius: "20px",
                    fontSize: "0.78rem",
                    fontWeight: 700,
                    color: "#fff",
                    background: catGradient,
                    boxShadow: "0 2px 12px rgba(0,0,0,0.3)",
                    zIndex: 2,
                  }}
                >
                  {t(`blog.category_${CATEGORY_TRANSLATION_KEYS[post.category] || "technology"}`)}
                </span>
              </div>

              <div className="blog-article-body">
                {/* Title + translate */}
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "16px", marginBottom: "20px" }}>
                  <h1 className="blog-article-title">
                    {isTranslated && translated ? translated.title : post.title}
                  </h1>
                  <button
                    onClick={() => toggle(post)}
                    title={
                      isTranslated
                        ? t("blog.show_original")
                        : t("blog.translate_to").replace("{lang}", LANG_LABELS[targetLang] || targetLang)
                    }
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      padding: "6px 14px",
                      borderRadius: "20px",
                      fontSize: "0.78rem",
                      fontWeight: 500,
                      border: "none",
                      cursor: "pointer",
                      background: isTranslated ? "var(--color-accent-glow)" : "var(--bg-secondary)",
                      color: isTranslated ? "var(--color-accent)" : "var(--color-text-muted)",
                      transition: "all 0.2s",
                      flexShrink: 0,
                      marginTop: "4px",
                    }}
                  >
                    {isLoading ? <Loader2 size={14} className="animate-spin" /> : <Globe size={14} />}
                    {isTranslated ? t("blog.original") : t("blog.translate")}
                  </button>
                </div>

                {translateError && (
                  <p style={{ color: "var(--color-danger)", fontSize: "0.85rem", marginBottom: "14px" }}>
                    {translateError}
                  </p>
                )}

                {/* Author + meta */}
                <div className="blog-article-meta-row">
                  <div className="blog-article-author">
                    <div
                      className="blog-article-avatar"
                      style={{ background: getAvatarColor(post.author.name) }}
                    >
                      {getInitials(post.author.name)}
                    </div>
                    <div>
                      <div className="blog-article-author-name">{post.author.name}</div>
                      <div className="blog-article-author-role">
                        {post.author.role === "recruiter"
                          ? t("blog.role_recruiter")
                          : post.author.plan === "premium"
                          ? t("blog.role_premium")
                          : t("blog.role_member")}
                      </div>
                    </div>
                  </div>
                  <div className="blog-article-date-row">
                    <Calendar size={13} style={{ color: "var(--color-accent)" }} />
                    <span>{formatDate(post.createdAt, t("blog.months"))}</span>
                    <span style={{ opacity: 0.4 }}>•</span>
                    <Clock size={13} style={{ color: "var(--color-accent)" }} />
                    <span>{readingTime(post.content, t("blog.reading_time"))}</span>
                  </div>
                </div>

                {/* Content prose */}
                <div className="blog-prose">
                  {(isTranslated && translated ? translated.content : post.content)
                    .split("\n")
                    .map((paragraph, i) => {
                      if (paragraph.startsWith("## ")) {
                        return (
                          <h2 key={i} className="blog-prose h2" style={{ fontSize: "1.3rem", fontWeight: 700, color: "var(--color-text)", margin: "30px 0 14px", letterSpacing: "-0.02em" }}>
                            {paragraph.replace("## ", "")}
                          </h2>
                        );
                      }
                      if (paragraph.trim() === "") return <br key={i} />;
                      return (
                        <p key={i} style={{ marginBottom: "18px", lineHeight: 1.8, color: "var(--color-text-secondary)" }}>
                          {paragraph}
                        </p>
                      );
                    })}
                </div>

                {/* Tags */}
                {post.tags.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "8px", marginBottom: "16px" }}>
                    {post.tags.map((tag, i) => (
                      <span key={i} className="blog-tag-chip">#{tag}</span>
                    ))}
                  </div>
                )}

                {/* Actions */}
                <div className="blog-article-actions">
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-text-secondary)", fontSize: "0.88rem" }}>
                    <MessageCircle size={18} style={{ color: "var(--color-accent)" }} />
                    <span>{post.comments.length} {t("blog.comments_count").replace("{count} ", "")}</span>
                  </div>
                  <button
                    className={`blog-action-btn${isLiked ? " liked" : ""}`}
                    onClick={handleLikePost}
                  >
                    <ThumbsUp size={18} />
                    <span>{post.likes.length} {t("blog.likes_count").replace("{count} ", "")}</span>
                  </button>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--color-text-secondary)", fontSize: "0.88rem" }}>
                    <Eye size={18} style={{ color: "var(--color-accent)" }} />
                    <span>{post.views} {t("blog.views_count").replace("{count} ", "")}</span>
                  </div>
                </div>
              </div>
            </motion.article>

            {/* Comment box */}
            {actionError && <p role="alert" style={{ color: "var(--color-danger)" }}>{actionError}</p>}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.25 }}
            >
              <CommentBox onSubmit={handleAddComment} commentCount={post.comments.length} disabled={!user || !token} />
            </motion.div>

            {/* Comment list */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.35 }}
            >
              <CommentList
                comments={post.comments}
                onReply={handleReply}
                onLike={handleLikeComment}
                disabled={!user || !token}
              />
            </motion.div>
          </div>

          {/* ── Sidebar ─────────────────────────────── */}
          <div className="lg:sticky lg:top-24 lg:h-fit">
            <BlogSidebar />
          </div>
        </div>
      </motion.div>
    </div>
  );
}
