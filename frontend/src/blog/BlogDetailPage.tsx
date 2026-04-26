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
import { useTranslation } from "./useTranslation";
import { LANG_LABELS } from "./translateService";
import {
  loadPosts, savePosts, formatDate, readingTime,
  CATEGORY_COLORS, getAvatarColor, getInitials,
  type BlogPost, type Comment,
} from "./blogStore";
import "../pages/BlogPage.css";

const CATEGORY_GRADIENTS: Record<string, string> = {
  Teknoloji: "linear-gradient(135deg, #3b82f6, #6366f1)",
  "Yapay Zeka": "linear-gradient(135deg, #10b981, #06b6d4)",
  Tasarım: "linear-gradient(135deg, #a855f7, #c084fc)",
  "Veri Bilimi": "linear-gradient(135deg, #f59e0b, #f97316)",
  Güvenlik: "linear-gradient(135deg, #ef4444, #f43f5e)",
  Cloud: "linear-gradient(135deg, #0ea5e9, #38bdf8)",
  Kariyer: "linear-gradient(135deg, #c084fc, #f472b6)",
};

export default function BlogDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { user, role, plan } = useAuth();
  const { lang, t } = useLanguage();
  const {
    isTranslated, isLoading, error: translateError, translated, targetLang, toggle,
  } = useTranslation(lang, t("blog.translation_failed"));
  const [post, setPost] = useState<BlogPost | null>(null);

  const email = (user as any)?.email || "";
  const userName =
    (user as any)?.user_metadata?.full_name ||
    email.split("@")[0] ||
    t("blog.anonymous");

  useEffect(() => {
    const posts = loadPosts();
    const found = posts.find(p => p.slug === slug);
    if (found) {
      const viewKey = `blog_viewed_${found.id}`;
      if (!sessionStorage.getItem(viewKey)) {
        found.views += 1;
        sessionStorage.setItem(viewKey, "1");
        savePosts(posts);
      }
      setPost({ ...found });
    }
  }, [slug]);

  function handleAddComment(text: string) {
    if (!post) return;
    const newComment: Comment = {
      id: `c-${Date.now()}`,
      author: { name: userName, email, role: role || "user", plan: plan || "free" },
      text,
      createdAt: new Date().toISOString(),
      likes: [],
      replies: [],
    };
    const updated = { ...post, comments: [...post.comments, newComment] };
    setPost(updated);
    const posts = loadPosts();
    const idx = posts.findIndex(p => p.id === post.id);
    if (idx >= 0) { posts[idx] = updated; savePosts(posts); }
  }

  function handleReply(commentId: string, text: string) {
    if (!post) return;
    const newReply = {
      id: `r-${Date.now()}`,
      author: { name: userName, email, role: role || "user", plan: plan || "free" },
      text,
      createdAt: new Date().toISOString(),
      likes: [] as string[],
    };
    const updatedComments = post.comments.map(c =>
      c.id === commentId ? { ...c, replies: [...c.replies, newReply] } : c
    );
    const updated = { ...post, comments: updatedComments };
    setPost(updated);
    const posts = loadPosts();
    const idx = posts.findIndex(p => p.id === post.id);
    if (idx >= 0) { posts[idx] = updated; savePosts(posts); }
  }

  function handleLikeComment(commentId: string) {
    if (!post || !email) return;
    const updatedComments = post.comments.map(c => {
      if (c.id === commentId) {
        const already = c.likes.includes(email);
        return { ...c, likes: already ? c.likes.filter(e => e !== email) : [...c.likes, email] };
      }
      return c;
    });
    const updated = { ...post, comments: updatedComments };
    setPost(updated);
    const posts = loadPosts();
    const idx = posts.findIndex(p => p.id === post.id);
    if (idx >= 0) { posts[idx] = updated; savePosts(posts); }
  }

  function handleLikePost() {
    if (!post || !email) return;
    const already = post.likes.includes(email);
    const updated = {
      ...post,
      likes: already ? post.likes.filter(e => e !== email) : [...post.likes, email],
    };
    setPost(updated);
    const posts = loadPosts();
    const idx = posts.findIndex(p => p.id === post.id);
    if (idx >= 0) { posts[idx] = updated; savePosts(posts); }
  }

  /* ── Not found ──────────────────────────────────── */
  if (!post) {
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
          <div style={{ fontSize: "3.5rem", marginBottom: "16px", opacity: 0.5 }}>📄</div>
          <p style={{ color: "var(--color-text-muted)", marginBottom: "16px" }}>{t("blog.post_not_found")}</p>
          <button className="blog-detail-back" onClick={() => navigate("/blog")}>
            <ArrowLeft size={16} />
            {t("blog.back_to_blog")}
          </button>
        </div>
      </div>
    );
  }

  const catGradient = CATEGORY_GRADIENTS[post.category] || "var(--gradient-accent)";
  const isLiked = post.likes.includes(email);

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
              <div className="blog-article-img-wrap">
                <img src={post.image} alt={post.title} className="blog-article-img" />
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
                  {post.category}
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
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.25 }}
            >
              <CommentBox onSubmit={handleAddComment} commentCount={post.comments.length} />
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
