import React, { useState, useEffect, useMemo } from "react";
import { Filter, PenLine, Sparkles, FileText } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../context/AuthContext";
import { useLanguage } from "../i18n/LanguageContext";
import BlogCard from "./components/BlogCard";
import BlogSidebar from "./components/BlogSidebar";
import TrendingArticles from "./components/TrendingArticles";
import CreatePostModal from "./components/CreatePostModal";
import { loadPosts, getUserPostCountToday, getDailyLimit, canUserPost, type BlogPost } from "./blogStore";
import "../pages/BlogPage.css";

const CATEGORY_KEYS = [
  { key: "all", value: "Tümü" },
  { key: "technology", value: "Teknoloji" },
  { key: "ai", value: "Yapay Zeka" },
  { key: "design", value: "Tasarım" },
  { key: "data_science", value: "Veri Bilimi" },
  { key: "security", value: "Güvenlik" },
  { key: "cloud", value: "Cloud" },
];

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.09 } },
};

const cardVariants = {
  hidden: { opacity: 0, y: 28 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" as const } },
};

export default function BlogPage() {
  const { user, plan, role } = useAuth();
  const { t } = useLanguage();
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("Tümü");
  const [searchQuery, setSearchQuery] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 4;

  useEffect(() => { setPosts(loadPosts()); }, []);

  const email = (user as any)?.email || "";
  const todayCount = getUserPostCountToday(email);
  const limit = getDailyLimit(plan, role);
  const canPost = canUserPost(email, plan, role);

  const filteredPosts = useMemo(() => {
    let result = posts;
    if (selectedCategory !== "Tümü") result = result.filter(p => p.category === selectedCategory);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(p =>
        p.title.toLowerCase().includes(q) ||
        p.summary.toLowerCase().includes(q) ||
        p.tags.some(tag => tag.toLowerCase().includes(q))
      );
    }
    return result;
  }, [posts, selectedCategory, searchQuery]);

  const totalPages = Math.max(1, Math.ceil(filteredPosts.length / pageSize));
  const pagedPosts = filteredPosts.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  useEffect(() => { setCurrentPage(1); }, [selectedCategory, searchQuery]);

  function handlePostCreated(newPost: BlogPost) {
    setPosts(prev => [newPost, ...prev]);
  }

  return (
    <div style={{ background: "var(--bg-primary)", color: "var(--color-text)", minHeight: "100vh" }}>
      {/* ── Hero ─────────────────────────────────────── */}
      <section className="blog-hero">
        <div className="blog-hero-orb blog-hero-orb-1" />
        <div className="blog-hero-orb blog-hero-orb-2" />
        <div className="blog-hero-orb blog-hero-orb-3" />
        <div className="blog-hero-inner">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: [0.4, 0, 0.2, 1] }}
          >
            <div className="blog-hero-badge">
              <Sparkles size={13} />
              {t("blog.page_title")}
            </div>
            <h1 className="blog-hero-title">{t("blog.page_title")}</h1>
            <p className="blog-hero-subtitle">{t("blog.page_subtitle")}</p>
          </motion.div>
        </div>
      </section>

      {/* ── Trending Articles from Dev.to ──────────── */}
      <TrendingArticles />

      {/* ── Main ─────────────────────────────────────── */}
      <div className="blog-main">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Posts Column */}
          <div className="lg:col-span-2">

            {/* Filter Row */}
            <motion.div
              className="blog-filter-row"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.15 }}
            >
              <Filter size={17} style={{ color: "var(--color-text-muted)", flexShrink: 0 }} />
              {CATEGORY_KEYS.map(({ key, value }) => (
                <button
                  key={key}
                  onClick={() => setSelectedCategory(value)}
                  className={`blog-filter-pill${selectedCategory === value ? " active" : ""}`}
                >
                  {t(`blog.category_${key}`)}
                </button>
              ))}
              <button
                onClick={() => setShowCreateModal(true)}
                disabled={!canPost}
                className="blog-create-btn"
                title={t("blog.post_quota")
                  .replace("{count}", String(todayCount))
                  .replace("{limit}", String(limit))}
              >
                <PenLine size={14} />
                {t("blog.create_post")}
              </button>
            </motion.div>

            {/* Blog Cards */}
            <AnimatePresence mode="wait">
              {pagedPosts.length === 0 ? (
                <motion.div
                  key="empty"
                  className="blog-empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <div className="blog-empty-icon"><FileText size={30} strokeWidth={1.6} /></div>
                  <p style={{ color: "var(--color-text-muted)" }}>{t("blog.no_posts_in_category")}</p>
                </motion.div>
              ) : (
                <motion.div
                  key={`${selectedCategory}-${currentPage}`}
                  className="blog-cards-list"
                  variants={containerVariants}
                  initial="hidden"
                  animate="visible"
                  exit={{ opacity: 0 }}
                >
                  {pagedPosts.map(post => (
                    <motion.div key={post.id} variants={cardVariants}>
                      <BlogCard post={post} />
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Pagination */}
            {totalPages > 1 && (
              <motion.div
                className="blog-pagination"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
              >
                <button
                  className="blog-page-btn"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                >
                  {t("blog.previous")}
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => (
                  <button
                    key={page}
                    className={`blog-page-btn${page === currentPage ? " active" : ""}`}
                    onClick={() => setCurrentPage(page)}
                  >
                    {page}
                  </button>
                ))}
                <button
                  className="blog-page-btn"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                >
                  {t("blog.next")}
                </button>
              </motion.div>
            )}
          </div>

          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="sticky top-24">
              <BlogSidebar onSearch={setSearchQuery} />
            </div>
          </div>
        </div>
      </div>

      <CreatePostModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handlePostCreated}
      />
    </div>
  );
}
