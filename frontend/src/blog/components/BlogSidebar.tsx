import React, { useMemo, useState } from "react";
import { Hash, Search, Tag, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../../i18n/LanguageContext";
import type { BlogPost } from "../blogStore";

const CATEGORY_KEYS: Record<string, string> = {
  Technology: "technology",
  "Artificial Intelligence": "ai",
  Design: "design",
  "Data Science": "data_science",
  Security: "security",
  Cloud: "cloud",
  Career: "career",
};

export default function BlogSidebar({
  onSearch,
  posts = [],
}: {
  onSearch?: (q: string) => void;
  posts?: BlogPost[];
}) {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  const popularPosts = useMemo(
    () => [...posts].sort((a, b) => b.views - a.views).slice(0, 4),
    [posts],
  );
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    posts.forEach(post => counts.set(post.category, (counts.get(post.category) || 0) + 1));
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [posts]);
  const tags = useMemo(
    () => Array.from(new Set(posts.flatMap(post => post.tags))).slice(0, 12),
    [posts],
  );

  return (
    <aside className="blog-sidebar">
      {onSearch && (
        <div className="blog-sidebar-card">
          <div className="blog-search-wrap">
            <input
              value={search}
              onChange={event => {
                setSearch(event.target.value);
                onSearch(event.target.value);
              }}
              placeholder={t("blog.search_placeholder")}
              className="blog-search-input"
            />
            <Search size={16} className="blog-search-icon" />
          </div>
        </div>
      )}

      {popularPosts.length > 0 && (
        <div className="blog-sidebar-card">
          <div className="blog-sidebar-heading">
            <TrendingUp size={17} style={{ color: "var(--color-accent)" }} />
            {t("blog.popular_posts")}
          </div>
          <div>
            {popularPosts.map(post => (
              <button
                key={post.id}
                type="button"
                className="blog-popular-item"
                onClick={() => navigate(`/blog/${post.slug}`)}
                style={{ width: "100%", textAlign: "left" }}
              >
                <div className="blog-popular-title">{post.title}</div>
                <div className="blog-popular-views">{post.views} {t("blog.views_suffix")}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {categories.length > 0 && (
        <div className="blog-sidebar-card">
          <div className="blog-sidebar-heading">
            <Hash size={17} style={{ color: "var(--color-accent)" }} />
            {t("blog.categories")}
          </div>
          <div>
            {categories.map(([category, count]) => (
              <div key={category} className="blog-cat-item">
                <span className="blog-cat-name">
                  {t(`blog.category_${CATEGORY_KEYS[category] || "technology"}`)}
                </span>
                <span className="blog-cat-count">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {tags.length > 0 && (
        <div className="blog-sidebar-card">
          <div className="blog-sidebar-heading">
            <Tag size={17} style={{ color: "var(--color-accent)" }} />
            {t("blog.tags")}
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {tags.map(tag => <span key={tag} className="blog-tag-chip">#{tag}</span>)}
          </div>
        </div>
      )}
    </aside>
  );
}
