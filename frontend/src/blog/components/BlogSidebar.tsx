import React, { useState } from "react";
import { Hash, Search, Tag, TrendingUp } from "lucide-react";
import { useLanguage } from "../../i18n/LanguageContext";

export default function BlogSidebar({ onSearch }: { onSearch?: (q: string) => void }) {
  const { t } = useLanguage();
  const [search, setSearch] = useState("");
  const [email, setEmail] = useState("");
  const [subscribed, setSubscribed] = useState(false);

  const POPULAR_POSTS = [
    { title: t("blog.sidebar_popular_1"), views: `12.5K ${t("blog.views_suffix")}` },
    { title: t("blog.sidebar_popular_2"), views: `10.2K ${t("blog.views_suffix")}` },
    { title: t("blog.sidebar_popular_3"), views: `8.7K ${t("blog.views_suffix")}` },
    { title: t("blog.sidebar_popular_4"), views: `7.3K ${t("blog.views_suffix")}` },
  ];

  const CATEGORIES_SIDEBAR = [
    { name: t("blog.sidebar_cat_career"), count: 24 },
    { name: t("blog.sidebar_cat_technology"), count: 18 },
    { name: t("blog.sidebar_cat_hr"), count: 15 },
    { name: t("blog.sidebar_cat_education"), count: 12 },
    { name: t("blog.sidebar_cat_entrepreneurship"), count: 9 },
  ];

  const tags: string[] = t("blog.sidebar_tags") || [];

  return (
    <aside className="blog-sidebar">
      {/* Search */}
      <div className="blog-sidebar-card">
        <div className="blog-search-wrap">
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); onSearch?.(e.target.value); }}
            placeholder={t("blog.search_placeholder")}
            className="blog-search-input"
          />
          <Search size={16} className="blog-search-icon" />
        </div>
      </div>

      {/* Popular Posts */}
      <div className="blog-sidebar-card">
        <div className="blog-sidebar-heading">
          <TrendingUp size={17} style={{ color: "var(--color-accent)" }} />
          {t("blog.popular_posts")}
        </div>
        <div>
          {POPULAR_POSTS.map((p, i) => (
            <div key={i} className="blog-popular-item">
              <div className="blog-popular-title">{p.title}</div>
              <div className="blog-popular-views">{p.views}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Categories */}
      <div className="blog-sidebar-card">
        <div className="blog-sidebar-heading">
          <Hash size={17} style={{ color: "var(--color-accent)" }} />
          {t("blog.categories")}
        </div>
        <div>
          {CATEGORIES_SIDEBAR.map((c, i) => (
            <div key={i} className="blog-cat-item">
              <span className="blog-cat-name">{c.name}</span>
              <span className="blog-cat-count">{c.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tags */}
      <div className="blog-sidebar-card">
        <div className="blog-sidebar-heading">
          <Tag size={17} style={{ color: "var(--color-accent)" }} />
          {t("blog.tags")}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          {tags.map((tag, i) => (
            <span
              key={i}
              className="blog-tag-chip"
              style={{ cursor: "pointer", transition: "all 0.2s" }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.background = "var(--color-accent)";
                (e.currentTarget as HTMLElement).style.color = "#fff";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.background = "var(--color-accent-glow)";
                (e.currentTarget as HTMLElement).style.color = "var(--color-accent)";
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Newsletter */}
      <div className="blog-sidebar-card blog-newsletter">
        <div className="blog-newsletter-title">{t("blog.newsletter")}</div>
        <p className="blog-newsletter-desc">{t("blog.newsletter_desc")}</p>
        {subscribed ? (
          <div className="blog-subscribed-msg">✓ {t("blog.subscribed")}</div>
        ) : (
          <>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder={t("blog.email_placeholder")}
              className="blog-newsletter-input"
            />
            <button
              onClick={() => { if (email.includes("@")) setSubscribed(true); }}
              className="blog-newsletter-btn"
            >
              {t("blog.subscribe")}
            </button>
          </>
        )}
      </div>
    </aside>
  );
}
