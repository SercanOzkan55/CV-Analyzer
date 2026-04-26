import React from 'react';
import { Filter } from 'lucide-react';

const CATEGORIES = ['Tümü', 'Teknoloji', 'Yapay Zeka', 'Tasarım', 'Veri Bilimi', 'Güvenlik', 'Cloud'];

export default function CategoryFilter({ selected, onSelect }: { selected: string; onSelect: (cat: string) => void }) {
  return (
    <div className="mb-0 flex items-center gap-3 overflow-x-auto pb-2">
      <div className="flex-shrink-0 text-gray-400">
        <Filter size={19} />
      </div>
      {CATEGORIES.map(cat => (
        <button
          key={cat}
          onClick={() => onSelect(cat)}
          className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-colors ${
            selected === cat
              ? 'bg-cyan-500 text-white'
              : 'border border-gray-800 bg-[#1a1f37] text-gray-400 hover:bg-[#252a45] hover:text-white'
          }`}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}
