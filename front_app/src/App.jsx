// App.jsx
import React, { useEffect, useMemo, useState } from "react";
import "./index.css";

const PAGE_SIZE = 15;

const STATUS_LABELS = {
  pending: "На проверке",
  approved: "Одобрена",
  rejected: "Отклонена",
};

function formatDate(value) {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "-";
    return d.toLocaleString("ru-RU", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "-";
  }
}

function App() {
  const [categories, setCategories] = useState([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [hasNewFilter, setHasNewFilter] = useState("all");

  const [currentPage, setCurrentPage] = useState(1);

  const [sortField, setSortField] = useState("id");
  const [sortDirection, setSortDirection] = useState("asc");

  // ===========================
  // Загрузка категорий с бэка
  // ===========================
  useEffect(() => {
    async function fetchCategories() {
      try {
        setLoading(true);
        setError(null);

        const res = await fetch("/api/categories");
        if (!res.ok) {
          throw new Error(`Ошибка загрузки категорий: ${res.status}`);
        }
        const data = await res.json();

        setCategories(data.categories || []);

        if (!selectedCategoryId && data.categories?.length) {
          setSelectedCategoryId(data.categories[0].id);
        }
      } catch (e) {
        console.error(e);
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }

    fetchCategories();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // При смене фильтров/поиска сбрасываем страницу
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, hasNewFilter]);

  // ===========================
  // Фильтрация
  // ===========================

  const filteredCategories = useMemo(() => {
    let result = categories;

    // Поиск по id и name
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      result = result.filter((c) => {
        const idStr = String(c.id || "");
        const nameStr = (c.name || "").toLowerCase();
        return idStr.includes(q) || nameStr.includes(q);
      });
    }

    // Фильтр по статусу
    if (statusFilter !== "all") {
      result = result.filter((c) => (c.status || "pending") === statusFilter);
    }

    // Фильтр по наличию новых товаров
    if (hasNewFilter === "yes") {
      result = result.filter((c) => c.hasNewItems === true);
    } else if (hasNewFilter === "no") {
      result = result.filter((c) => !c.hasNewItems);
    }

    return result;
  }, [categories, searchQuery, statusFilter, hasNewFilter]);

  // ===========================
  // Сортировка
  // ===========================

  const sortedCategories = useMemo(() => {
    const list = [...filteredCategories];

    list.sort((a, b) => {
      const dir = sortDirection === "asc" ? 1 : -1;

      switch (sortField) {
        case "id": {
          const av = Number(a.id) || 0;
          const bv = Number(b.id) || 0;
          return (av - bv) * dir;
        }
        case "name": {
          const av = (a.name || "").toLowerCase();
          const bv = (b.name || "").toLowerCase();
          if (av < bv) return -1 * dir;
          if (av > bv) return 1 * dir;
          return 0;
        }
        case "generatedAt": {
          const av = a.generatedAt ? new Date(a.generatedAt).getTime() : 0;
          const bv = b.generatedAt ? new Date(b.generatedAt).getTime() : 0;
          return (av - bv) * dir;
        }
        case "status": {
          const av = (a.status || "").toLowerCase();
          const bv = (b.status || "").toLowerCase();
          if (av < bv) return -1 * dir;
          if (av > bv) return 1 * dir;
          return 0;
        }
        case "rating": {
          const av = a.rating ?? -1;
          const bv = b.rating ?? -1;
          return (av - bv) * dir;
        }
        case "hasNew": {
          const av = a.hasNewItems ? 1 : 0;
          const bv = b.hasNewItems ? 1 : 0;
          if (av === bv) {
            const ac = a.newItemsCount || 0;
            const bc = b.newItemsCount || 0;
            return (ac - bc) * dir;
          }
          return (av - bv) * dir;
        }
        default:
          return 0;
      }
    });

    return list;
  }, [filteredCategories, sortField, sortDirection]);

  const totalPages = Math.max(1, Math.ceil(sortedCategories.length / PAGE_SIZE));
  const page = Math.min(Math.max(1, currentPage), totalPages);
  const offset = (page - 1) * PAGE_SIZE;
  const pageCategories = sortedCategories.slice(offset, offset + PAGE_SIZE);

  // ===========================
  // Детали выбранной категории
  // ===========================

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) || null,
    [categories, selectedCategoryId]
  );

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  const sortIcon = (field) => {
    if (sortField !== field) return "⇵";
    return sortDirection === "asc" ? "↑" : "↓";
  };

  // ===========================
  // Рендер
  // ===========================

  return (
    <div className="app-root">
      <header className="app-header">
        <h1>Умная агрегация товарных категорий</h1>
        <p className="app-subtitle">
          Категории, сгенерированные моделью, и их характеристики
        </p>
      </header>

      <main className="app-main">
        {/* Левая панель: список категорий (2/3 ширины задаётся в CSS) */}
        <section className="left-panel">
          <div className="panel-header">
            <h2>Категории</h2>
            <div className="filters-row">
              <input
                type="text"
                className="search-input"
                placeholder="Поиск по ID или названию…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />

              <select
                className="filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="all">Все статусы</option>
                <option value="pending">На проверке</option>
                <option value="approved">Одобрена</option>
                <option value="rejected">Отклонена</option>
              </select>

              <select
                className="filter-select"
                value={hasNewFilter}
                onChange={(e) => setHasNewFilter(e.target.value)}
              >
                <option value="all">Все категории</option>
                <option value="yes">Есть новые товары</option>
                <option value="no">Без новых товаров</option>
              </select>
            </div>
          </div>

          {loading && <div className="info-block">Загрузка категорий…</div>}
          {error && <div className="error-block">Ошибка: {error}</div>}

          {!loading && !error && (
            <>
              <div className="table-wrapper">
                <table className="categories-table">
                  <thead>
                    <tr>
                      <th onClick={() => handleSort("id")}>
                        ID категории <span className="sort-icon">{sortIcon("id")}</span>
                      </th>
                      <th onClick={() => handleSort("name")}>
                        Название категории{" "}
                        <span className="sort-icon">{sortIcon("name")}</span>
                      </th>
                      <th>Описание</th>
                      <th onClick={() => handleSort("generatedAt")}>
                        Дата генерации{" "}
                        <span className="sort-icon">
                          {sortIcon("generatedAt")}
                        </span>
                      </th>
                      <th onClick={() => handleSort("hasNew")}>
                        Новые товары{" "}
                        <span className="sort-icon">{sortIcon("hasNew")}</span>
                      </th>
                      <th onClick={() => handleSort("status")}>
                        Статус{" "}
                        <span className="sort-icon">{sortIcon("status")}</span>
                      </th>
                      <th onClick={() => handleSort("rating")}>
                        Оценка{" "}
                        <span className="sort-icon">{sortIcon("rating")}</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageCategories.length === 0 && (
                      <tr>
                        <td colSpan={7} className="empty-cell">
                          Ничего не найдено по текущим фильтрам.
                        </td>
                      </tr>
                    )}

                    {pageCategories.map((cat) => {
                      const isSelected = cat.id === selectedCategoryId;
                      const rowClass = [
                        "table-row",
                        isSelected ? "row-selected" : "",
                        cat.hasNewItems ? "row-has-new" : "",
                      ]
                        .filter(Boolean)
                        .join(" ");

                      return (
                        <tr
                          key={cat.id}
                          className={rowClass}
                          onClick={() => setSelectedCategoryId(cat.id)}
                        >
                          <td className="cell-id">{cat.id}</td>
                          <td className="cell-name">{cat.name}</td>
                          <td className="cell-description">
                            {cat.shortDescription || "—"}
                          </td>
                          <td className="cell-date">
                            {formatDate(cat.generatedAt)}
                          </td>
                          <td className="cell-new">
                            {cat.hasNewItems ? (
                              <span className="badge badge-alert">
                                Да{cat.newItemsCount
                                  ? ` (+${cat.newItemsCount})`
                                  : ""}
                              </span>
                            ) : (
                              <span className="badge badge-ok">Нет</span>
                            )}
                          </td>
                          <td className="cell-status">
                            {STATUS_LABELS[cat.status] || "На проверке"}
                          </td>
                          <td className="cell-rating">
                            {cat.rating != null ? cat.rating : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Пагинация */}
              <div className="pagination">
                <button
                  className="page-btn"
                  disabled={page <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                >
                  «
                </button>
                <span className="page-info">
                  Стр. {page} из {totalPages} (всего {sortedCategories.length})
                </span>
                <button
                  className="page-btn"
                  disabled={page >= totalPages}
                  onClick={() =>
                    setCurrentPage((p) => Math.min(totalPages, p + 1))
                  }
                >
                  »
                </button>
              </div>
            </>
          )}
        </section>

        {/* Правая панель: детали категории */}
        <section className="right-panel">
          <div className="panel-header">
            <h2>Детали категории</h2>
          </div>

          {!selectedCategory && (
            <div className="info-block">
              Выберите категорию слева, чтобы посмотреть детали.
            </div>
          )}

          {selectedCategory && (
            <div className="category-details">
              <div className="details-main">
                <h3>
                  [{selectedCategory.id}] {selectedCategory.name}
                </h3>
                <p className="details-description">
                  {selectedCategory.shortDescription || "Описание не задано."}
                </p>

                <div className="details-meta">
                  <div>
                    <span className="meta-label">Дата генерации:</span>{" "}
                    <span className="meta-value">
                      {formatDate(selectedCategory.generatedAt)}
                    </span>
                  </div>
                  <div>
                    <span className="meta-label">Статус:</span>{" "}
                    <span className="meta-value">
                      {STATUS_LABELS[selectedCategory.status] ||
                        "На проверке"}
                    </span>
                  </div>
                  <div>
                    <span className="meta-label">Оценка:</span>{" "}
                    <span className="meta-value">
                      {selectedCategory.rating != null
                        ? selectedCategory.rating
                        : "—"}
                    </span>
                  </div>
                  <div>
                    <span className="meta-label">Новые товары:</span>{" "}
                    <span className="meta-value">
                      {selectedCategory.hasNewItems ? (
                        <>
                          есть
                          {selectedCategory.newItemsCount
                            ? ` (${selectedCategory.newItemsCount})`
                            : ""}
                        </>
                      ) : (
                        "нет"
                      )}
                    </span>
                  </div>
                  <div>
                    <span className="meta-label">Всего СТЕ в категории:</span>{" "}
                    <span className="meta-value">
                      {selectedCategory.productIds?.length || 0}
                    </span>
                  </div>
                </div>
              </div>

              <div className="details-features">
                <h4>Уникальные характеристики категории</h4>
                {(!selectedCategory.features ||
                  selectedCategory.features.length === 0) && (
                  <div className="info-block small">
                    Для этой категории ещё нет выделенных характеристик.
                  </div>
                )}
                {selectedCategory.features &&
                  selectedCategory.features.length > 0 && (
                    <ul className="features-list">
                      {selectedCategory.features.map((f, idx) => (
                        <li key={`${f.key}-${f.value}-${idx}`}>
                          <span className="feature-key">{f.key}:</span>{" "}
                          <span className="feature-value">{f.value}</span>
                        </li>
                      ))}
                    </ul>
                  )}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
