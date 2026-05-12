import React, { useEffect, useState } from 'react';

function App() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Интеграция с Telegram Web App
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand(); // Разворачиваем приложение на весь экран
      // Устанавливаем цвет темы (опционально)
      tg.setHeaderColor('secondary_bg_color');
    }

    // Загружаем актуальный JSON из твоего репозитория
    // Используем raw.githubusercontent для прямого доступа к файлу
    fetch('https://raw.githubusercontent.com/Smokearbuz/HantavirusBot/master/data/stats.json')
      .then((res) => res.json())
      .then((data) => {
        setStats(data);
      })
      .catch((err) => {
        console.error("Ошибка при получении данных:", err);
      });
  }, []);

  // Состояние загрузки (Spin-лоадер на Tailwind)
  if (!stats) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-red-600"></div>
        <p className="mt-4 text-gray-500 font-medium">Загрузка данных...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 font-sans text-gray-900 pb-10">
      {/* Шапка приложения */}
      <header className="mb-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-black text-red-600 tracking-tighter">HANTAVIRUS 2026</h1>
          <span className="bg-red-100 text-red-700 text-[10px] px-2 py-1 rounded-full font-bold uppercase">Live</span>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Последнее обновление: <span className="text-gray-600">{stats.global.last_update}</span>
        </p>
      </header>

      {/* Основные карточки (Глобально) */}
      <div className="grid grid-cols-2 gap-4 mb-8">
        <div className="bg-white p-5 rounded-3xl shadow-sm border border-gray-100">
          <p className="text-[10px] text-gray-400 uppercase font-bold tracking-widest mb-1">Случаев</p>
          <p className="text-3xl font-black text-gray-800">{stats.global.total.toLocaleString()}</p>
          <p className="text-[10px] text-orange-500 mt-1 font-medium">+{stats.global.suspected} под подозрением</p>
        </div>
        <div className="bg-white p-5 rounded-3xl shadow-sm border border-gray-100">
          <p className="text-[10px] text-gray-400 uppercase font-bold tracking-widest mb-1">Смертей</p>
          <p className="text-3xl font-black text-black">{stats.global.deaths.toLocaleString()}</p>
          <p className="text-[10px] text-gray-400 mt-1 font-medium">Летальность: {((stats.global.deaths / stats.global.total) * 100).toFixed(1)}%</p>
        </div>
      </div>

      {/* Список стран */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-bold uppercase text-gray-500 tracking-widest">География</h2>
        <span className="text-[10px] text-gray-400">{Object.keys(stats.countries).length} стран</span>
      </div>
      
      <div className="space-y-2">
        {Object.entries(stats.countries).map(([country, data]) => (
          <div key={country} className="bg-white flex items-center justify-between p-4 rounded-2xl shadow-sm border border-gray-50 active:scale-[0.98] transition-transform">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-red-500"></div>
              <span className="font-bold text-gray-700">{country}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm font-black text-gray-900">{data.total}</p>
                <p className="text-[9px] text-gray-400 uppercase">Случаев</p>
              </div>
              <div className="text-right border-l pl-4 border-gray-100">
                <p className="text-sm font-black text-red-600">{data.deaths}</p>
                <p className="text-[9px] text-gray-400 uppercase">💀</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Футер-заглушка для красоты */}
      <footer className="mt-10 text-center">
        <p className="text-[10px] text-gray-300 uppercase tracking-[0.2em]">Data provided by Global.health & Hondius Project</p>
      </footer>
    </div>
  );
}

export default App;