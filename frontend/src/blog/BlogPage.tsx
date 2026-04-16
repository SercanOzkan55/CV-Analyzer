import React from "react";
import { useState, useEffect } from "react";
import BlogCard from "./components/BlogCard";
import BlogSidebar from "./components/BlogSidebar";
import CategoryFilter from "./components/CategoryFilter";

type Post = {
  id: number;
  title: string;
  summary: string;
  category: string;
  slug: string;
  image: string;
};

export default function BlogPage() {
  const [posts, setPosts] = useState<Post[]>([]);

  useEffect(() => {
    const data: Post[] = [
      {
        id: 1,
        title: "Yazılım geliştirmede en iyi pratikler",
        summary: "Clean code, test ve kalite standartları",
        category: "Teknoloji",
        slug: "en-iyi-pratikler",
        image: "https://picsum.photos/900/300",
      },
      {
        id: 2,
        title: "Kariyer planlaması nasıl yapılır?",
        summary: "Hedef belirleme ve gelişim yolları",
        category: "Kariyer",
        slug: "kariyer-planlamasi",
        image: "https://picsum.photos/900/301",
      },
    ];

    setPosts(data);
  }, []);

  return (
    <div className="min-h-screen bg-[#0b1220] text-white">
      <div className="max-w-7xl mx-auto px-6 py-10">

        <h1 className="text-4xl font-bold mb-2">
          Blog & Sohbet
        </h1>

        <p className="text-gray-400 mb-6">
          Kariyer, teknoloji ve iş dünyası hakkında içerikler
        </p>

        <CategoryFilter />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">

          <div className="lg:col-span-2 space-y-6">

            {posts.map((post: Post) => (
              <BlogCard key={post.id} post={post} />
            ))}

          </div>

          <BlogSidebar />

        </div>
      </div>
    </div>
  );
}