// src/App.jsx
import React, { useMemo, useState, useEffect, useRef } from "react";
import "./styles.css";

const API_BASE = "https://faso312.ru";
const PAGE_SIZE = 10;

const formatDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString("ru-RU") : "—";

const statusLabel = (status) => {
  if (status === "approved") return "Одобрено";
  if (status === "rejected") return "Не одобрено";
  return "Не обработано";
};

// нормализуем статус под ключ фильтра
const getStatusKey = (status) => {
  if (status === "approved" || status === "rejected") return status;
  return "pending";
};

/* ===================== ЗВЁЗДОЧКИ ===================== */

function StarRating({ value = 0, onChange }) {
  const stars = [1, 2, 3, 4, 5];

  return (
    <div className="stars">
      {stars.map((s) => (
        <button
          key={s}
          type="button"
          className={`star ${value >= s ? "star--active" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onChange?.(s);
          }}
        >
          ★
        </button>
      ))}
      <button
        type="button"
        className="star-reset"
        onClick={(e) => {
          e.stopPropagation();
          onChange?.(0);
        }}
      >
        ✕
      </button>
    </div>
  );
}

/* ===================== КАРТОЧКА КАТЕГОРИИ ===================== */

function CategoryCard({
  category,
  onRegenerate,
  onRatingChange,
  onUpdateCategory,
  onShowProducts,
  isRegenerating,
}) {
  const {
    id,
    name,
    description,
    createdAt,
    generatedAt,
    status,
    rating,
    features = [],
    productIds = [],
    hasNewItems,
    newItemsCount,
    hasUntrainedItems,
    untrainedItemsCount,
  } = category;

  const [descriptionDraft, setDescriptionDraft] = useState(description || "");
  const [featuresDraft, setFeaturesDraft] = useState(
    features.map((f) => f.name).join("\n")
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDescriptionDraft(description || "");
  }, [description, id]);

  useEffect(() => {
    setFeaturesDraft(features.map((f) => f.name).join("\n"));
  }, [features, id]);

  const handleSave = async () => {
    const trimmedDesc = descriptionDraft.trim();
    const lines = featuresDraft
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const payload = {
      description: trimmedDesc || null,
      features: lines.map((name) => ({ name })),
    };

    setSaving(true);
    try {
      await onUpdateCategory?.(id, payload);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title-block">
          <div className="card-title-main">{name}</div>
          <div className="card-title-sub">ID: {id}</div>
        </div>

        <div className="card-header-right">
          <div className="card-status">
            <span
              className={`status-badge ${
                status === "approved"
                  ? "status-badge--approved"
                  : status === "rejected"
                  ? "status-badge--rejected"
                  : "status-badge--pending"
              }`}
            >
              {statusLabel(status)}
            </span>
          </div>
          <div className="card-rating">
            <StarRating value={rating ?? 0} onChange={(v) => onRatingChange?.(id, v)} />
          </div>
        </div>
      </div>

      <div className="card-meta">
        <div className="card-meta-item">
          <span className="card-meta-label">Дата генерации:</span>
          <span>{formatDate(generatedAt || createdAt)}</span>
        </div>
        <div className="card-meta-item">
          <span className="card-meta-label">Создана:</span>
          <span>{formatDate(createdAt)}</span>
        </div>
      </div>

      <div className="card-section">
        <div className="card-section-title">Состояние категории</div>
        <div className="card-badges-row">
          <div className="card-badge">
            Новые товары:{" "}
            {hasNewItems ? (
              <span className="new-items-badge">
                Есть новые ({newItemsCount ?? 0})
              </span>
            ) : (
              <span className="new-items-badge new-items-badge--none">
                Нет
              </span>
            )}
          </div>

          <div className="card-badge">
            Обучение:
            {hasUntrainedItems ? (
              <span className="training-warning">
                Необученных СТЕ: {untrainedItemsCount ?? 0}
              </span>
            ) : (
              <span className="training-ok">Все СТЕ использованы в обучении</span>
            )}
          </div>
        </div>
      </div>

      <div className="card-section">
        <div className="card-section-title">Краткое описание</div>
        <textarea
          className="input card-description-input"
          rows={4}
          placeholder="Опишите, что за категория и по каким признакам товары должны в неё попадать."
          value={descriptionDraft}
          onChange={(e) => setDescriptionDraft(e.target.value)}
        />
      </div>

      <div className="card-section">
        <div className="card-section-title">Основные характеристики</div>
        {features.length === 0 && !featuresDraft.trim() ? (
          <p className="card-section-empty">
            Для этой категории пока нет сохранённых характеристик.
          </p>
        ) : null}
        <textarea
          className="input card-features-input"
          rows={4}
          placeholder="Каждая характеристика с новой строки"
          value={featuresDraft}
          onChange={(e) => setFeaturesDraft(e.target.value)}
        />
      </div>

      <div className="card-section">
        <div className="card-section-title">Товары в категории</div>
        <div className="products-count-row">
          <span className="products-count">
            Количество СТЕ в категории: {productIds?.length ?? 0}
          </span>
        </div>
      </div>

      <div className="card-footer">
        <div className="card-footer-left">
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={() => onShowProducts?.()}
            disabled={!productIds || productIds.length === 0}
          >
            Показать все СТЕ
          </button>
        </div>
        <div className="card-footer-right">
          <button
            className="btn btn-secondary"
            type="button"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Сохранение…" : "Сохранить изменения"}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => onRegenerate?.(id)}
            type="button"
            disabled={isRegenerating}
          >
            {isRegenerating ? "Перегенерация…" : "Перегенерировать категорию"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ===================== МОДАЛКА С ПРОДУКТАМИ (СТЕ) ===================== */

function ProductsModal({ data, onClose, onRegenerateSelected }) {
  const {
    id: categoryId,
    name,
    productIds = [],
    products = [],
    loading,
    error,
  } = data || {};

  const [selectedIds, setSelectedIds] = useState(new Set(productIds));

  // глобальный поиск
  const [searchText, setSearchText] = useState("");

  // фильтры по производителю/стране через чекбоксы
  const [producerFilterOpen, setProducerFilterOpen] = useState(false);
  const [countryFilterOpen, setCountryFilterOpen] = useState(false);
  const [producerFilterValues, setProducerFilterValues] = useState(
    () => new Set()
  );
  const [countryFilterValues, setCountryFilterValues] = useState(
    () => new Set()
  );

  const EMPTY_KEY = "__EMPTY__";

  const normalizeOptionKey = (value) => {
    const v = (value || "").toString().trim();
    return v === "" ? EMPTY_KEY : v;
  };

  const getOptionLabel = (key) => {
    if (key === EMPTY_KEY) return "пусто";
    return key;
  };

  useEffect(() => {
    setSelectedIds(new Set(productIds));
    setSearchText("");
    setProducerFilterOpen(false);
    setCountryFilterOpen(false);
    setProducerFilterValues(new Set());
    setCountryFilterValues(new Set());
  }, [categoryId, productIds]);

  const producerOptions = useMemo(() => {
    const set = new Set();
    (products || []).forEach((p) => {
      set.add(normalizeOptionKey(p.producer));
    });
    return Array.from(set).sort((a, b) =>
      getOptionLabel(a).localeCompare(getOptionLabel(b), "ru", {
        sensitivity: "base",
      })
    );
  }, [products]);

  const countryOptions = useMemo(() => {
    const set = new Set();
    (products || []).forEach((p) => {
      set.add(normalizeOptionKey(p.country));
    });
    return Array.from(set).sort((a, b) =>
      getOptionLabel(a).localeCompare(getOptionLabel(b), "ru", {
        sensitivity: "base",
      })
    );
  }, [products]);

  const filteredProducts = useMemo(() => {
    let list = products || [];
    if (!list.length) return [];

    const q = searchText.trim().toLowerCase();
    const producerSet = producerFilterValues;
    const countrySet = countryFilterValues;

    return list.filter((p) => {
      const specsText =
        typeof p.raw_specs === "string" ? p.raw_specs.toLowerCase() : "";

      if (q) {
        const haystack = [
          String(p.id || ""),
          p.name || "",
          p.producer || "",
          p.country || "",
          specsText || "",
        ]
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      if (producerSet.size > 0) {
        const key = normalizeOptionKey(p.producer);
        if (!producerSet.has(key)) return false;
      }

      if (countrySet.size > 0) {
        const key = normalizeOptionKey(p.country);
        if (!countrySet.has(key)) return false;
      }

      return true;
    });
  }, [products, searchText, producerFilterValues, countryFilterValues]);

  const toggleOne = (pid, checked) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(pid);
      else next.delete(pid);
      return next;
    });
  };

  const allVisibleChecked =
    filteredProducts.length > 0 &&
    filteredProducts.every((p) => selectedIds.has(p.id));

  const toggleAll = (checked) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        filteredProducts.forEach((p) => next.add(p.id));
      } else {
        filteredProducts.forEach((p) => next.delete(p.id));
      }
      return next;
    });
  };

  const toggleFilterValue = (kind, key, checked) => {
    const updater =
      kind === "producer" ? setProducerFilterValues : setCountryFilterValues;

    updater((prev) => {
      const next = new Set(prev);
      if (checked) next.add(key);
      else next.delete(key);
      return next;
    });
  };

  const selectAllFilterValues = (kind, options) => {
    const updater =
      kind === "producer" ? setProducerFilterValues : setCountryFilterValues;
    updater(new Set(options));
  };

  const clearFilterValues = (kind) => {
    const updater =
      kind === "producer" ? setProducerFilterValues : setCountryFilterValues;
    updater(new Set());
  };

  const handleRegenerateClick = async () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) {
      if (
        !window.confirm(
          "Вы не выбрали ни одного товара. Перегенерировать по ВСЕМ товарам категории?"
        )
      ) {
        return;
      }
      await onRegenerateSelected?.(categoryId);
    } else {
      await onRegenerateSelected?.(categoryId, ids);
    }
    onClose();
  };

  if (!data) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal modal-wide"
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        <div className="modal-header">
          <h2 className="modal-title">СТЕ в категории «{name}»</h2>
          <button
            type="button"
            className="btn btn-ghost btn-small"
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        <div className="modal-body">
          {loading ? (
            <p>Загрузка товаров…</p>
          ) : error ? (
            <p className="products-error">{error}</p>
          ) : productIds.length === 0 ? (
            <p>В этой категории пока нет СТЕ.</p>
          ) : products.length === 0 ? (
            <p>По указанным ID товаров в БД ничего не найдено.</p>
          ) : (
            <>
              <div className="modal-filters">
                <div className="modal-filters-counter modal-filters-counter--top">
                  Всего: {products.length} • По фильтру:{" "}
                  {filteredProducts.length}
                </div>

                <div className="modal-filters-main">
                  <label className="modal-filters-label">
                    Поиск по таблице (ID, наименование, производитель, страна,
                    характеристики)
                  </label>
                  <input
                    className="input modal-filters-input"
                    placeholder="Введите текст для поиска…"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                  />
                </div>
              </div>

              <div className="products-table-wrapper">
                <table className="products-table">
                  <thead>
                    <tr>
                      <th className="products-col-checkbox">
                        <input
                          type="checkbox"
                          checked={
                            filteredProducts.length > 0 && allVisibleChecked
                          }
                          onChange={(e) => toggleAll(e.target.checked)}
                        />
                      </th>
                      <th>ID</th>
                      <th>Наименование</th>
                      <th>
                        <div className="col-header-with-filter">
                          <span>Производитель</span>
                          <button
                            type="button"
                            className={
                              producerFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={() =>
                              setProducerFilterOpen((v) => !v)
                            }
                          >
                            ▾
                          </button>
                          {producerFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по производителю
                              </div>
                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAllFilterValues(
                                      "producer",
                                      producerOptions
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    clearFilterValues("producer")
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>
                              <div className="col-filter-options">
                                {producerOptions.map((key) => {
                                  const label = getOptionLabel(key);
                                  const checked =
                                    producerFilterValues.has(key);
                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleFilterValue(
                                            "producer",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{label}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>
                      <th>
                        <div className="col-header-with-filter">
                          <span>Страна</span>
                          <button
                            type="button"
                            className={
                              countryFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={() => setCountryFilterOpen((v) => !v)}
                          >
                            ▾
                          </button>
                          {countryFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по стране
                              </div>
                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAllFilterValues(
                                      "country",
                                      countryOptions
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    clearFilterValues("country")
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>
                              <div className="col-filter-options">
                                {countryOptions.map((key) => {
                                  const label = getOptionLabel(key);
                                  const checked =
                                    countryFilterValues.has(key);
                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleFilterValue(
                                            "country",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{label}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>
                      <th>Характеристики</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="table-empty">
                          Нет товаров, подходящих под фильтр
                        </td>
                      </tr>
                    ) : (
                      filteredProducts.map((p) => {
                        const specsText =
                          typeof p.raw_specs === "string" ? p.raw_specs : "";
                        const specsLines = specsText
                          ? specsText
                              .split(";")
                              .map((s) => s.trim())
                              .filter(Boolean)
                          : [];

                        const untrained = p.is_used_for_training === false;

                        return (
                          <tr
                            key={p.id}
                            className={
                              untrained
                                ? "product-row product-row--untrained"
                                : "product-row"
                            }
                          >
                            <td className="products-col-checkbox">
                              <input
                                type="checkbox"
                                checked={selectedIds.has(p.id)}
                                onChange={(e) =>
                                  toggleOne(p.id, e.target.checked)
                                }
                              />
                            </td>
                            <td className="products-col-id">{p.id}</td>
                            <td className="products-col-name">
                              {p.name || "—"}
                              {untrained && (
                                <span className="product-tag-untrained">
                                  не использован в обучении
                                </span>
                              )}
                            </td>
                            <td className="products-col-producer">
                              {p.producer || "—"}
                            </td>
                            <td className="products-col-country">
                              {p.country || "—"}
                            </td>
                            <td className="products-col-specs">
                              {specsLines.length === 0 ? (
                                <span>—</span>
                              ) : (
                                specsLines.map((line, idx) => (
                                  <div
                                    key={idx}
                                    className="products-spec-line"
                                  >
                                    {line}
                                  </div>
                                ))
                              )}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>

              <div className="modal-footer">
                <div className="modal-footer-info">
                  Выбрано товаров: {selectedIds.size} из {products.length}
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleRegenerateClick}
                >
                  Перегенерировать по выбранным
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ===================== ГЛАВНОЕ ПРИЛОЖЕНИЕ ===================== */

function App() {
  const [categories, setCategories] = useState([]);
  const [regeneratingIds, setRegeneratingIds] = useState(new Set());
  const [selectedCategoryId, setSelectedCategoryId] = useState(null);

  // фильтры слева
  const [search, setSearch] = useState("");
  const [filterId, setFilterId] = useState("");
  const [filterStatus, setFilterStatus] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // модалка с товарами
  const [productsModal, setProductsModal] = useState(null);

  // умный поиск
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartError, setSmartError] = useState("");
  const [smartResultIds, setSmartResultIds] = useState([]);
  const smartTimeoutRef = useRef(null);

  // Excel-фильтры в шапке таблицы категорий
  const [statusFilterOpen, setStatusFilterOpen] = useState(false);
  const [ratingFilterOpen, setRatingFilterOpen] = useState(false);
  const [statusFilterValues, setStatusFilterValues] = useState(
    () => new Set()
  );
  const [ratingFilterValues, setRatingFilterValues] = useState(
    () => new Set()
  );

  /* ===== Загрузка категорий ===== */

  useEffect(() => {
    async function loadCategories() {
      try {
        setLoading(true);
        setError("");
        const res = await fetch(`${API_BASE}/api/categories`);
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        const cats = data.categories || [];
        setCategories(cats);
        if (cats.length > 0) {
          setSelectedCategoryId(cats[0].id);
        }
      } catch (e) {
        console.error("Ошибка загрузки категорий", e);
        setError("Не удалось загрузить категории");
      } finally {
        setLoading(false);
      }
    }

    loadCategories();
  }, []);

  // сброс страницы при изменении фильтров
  useEffect(() => {
    setCurrentPage(1);
  }, [
    search,
    filterId,
    filterStatus,
    dateFrom,
    dateTo,
    categories,
    smartResultIds,
    statusFilterValues,
    ratingFilterValues,
  ]);

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === selectedCategoryId) ?? null,
    [categories, selectedCategoryId]
  );

  // опции для Excel-фильтров
  const statusOptions = useMemo(() => {
    const set = new Set();
    categories.forEach((cat) => {
      set.add(getStatusKey(cat.status));
    });
    return Array.from(set);
  }, [categories]);

  const ratingOptions = useMemo(() => {
    const set = new Set();
    categories.forEach((cat) => {
      const r = typeof cat.rating === "number" ? cat.rating : 0;
      set.add(String(r));
    });
    return Array.from(set).sort((a, b) => Number(a) - Number(b));
  }, [categories]);

  /* ===== Фильтрация категорий ===== */

  const filteredCategories = useMemo(() => {
    const base = categories.filter((cat) => {
      // 1. умный поиск по ID
      if (smartResultIds.length > 0 && !smartResultIds.includes(cat.id)) {
        return false;
      }

      // 2. обычный поиск по имени/описанию, если умный поиск ничего не вернул
      if (
        smartResultIds.length === 0 &&
        search &&
        !`${cat.name} ${cat.description || ""}`
          .toLowerCase()
          .includes(search.toLowerCase())
      ) {
        return false;
      }

      // 3. фильтр по ID
      if (filterId && !String(cat.id).includes(filterId.trim())) return false;

      // 4. фильтр по статусу (селект)
      if (filterStatus !== "all") {
        if (filterStatus === "pending") {
          if (cat.status === "approved" || cat.status === "rejected") {
            return false;
          }
        } else if (cat.status !== filterStatus) {
          return false;
        }
      }

      // 5. фильтр по дате
      const dateField = cat.createdAt || cat.generatedAt;
      if (dateFrom && dateField) {
        if (new Date(dateField) < new Date(dateFrom)) return false;
      }
      if (dateTo && dateField) {
        if (new Date(dateField) > new Date(dateTo)) return false;
      }

      // 6. Excel-фильтр по рейтингу
      if (ratingFilterValues.size > 0) {
        const key = String(
          typeof cat.rating === "number" ? cat.rating : 0
        );
        if (!ratingFilterValues.has(key)) return false;
      }

      // 7. Excel-фильтр по статусу
      if (statusFilterValues.size > 0) {
        const key = getStatusKey(cat.status);
        if (!statusFilterValues.has(key)) return false;
      }

      return true;
    });

    // если умный поиск активен — порядок не меняем
    if (smartResultIds.length > 0) {
      return base;
    }

    // иначе поднимаем категории с необученными СТЕ
    const sorted = [...base].sort((a, b) => {
      const au = !!a.hasUntrainedItems;
      const bu = !!b.hasUntrainedItems;
      if (au === bu) return 0;
      return au ? -1 : 1;
    });

    return sorted;
  }, [
    categories,
    search,
    filterId,
    filterStatus,
    dateFrom,
    dateTo,
    smartResultIds,
    statusFilterValues,
    ratingFilterValues,
  ]);

  const totalPages = useMemo(
    () =>
      filteredCategories.length > 0
        ? Math.ceil(filteredCategories.length / PAGE_SIZE)
        : 1,
    [filteredCategories.length]
  );

  const paginatedCategories = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredCategories.slice(start, start + PAGE_SIZE);
  }, [filteredCategories, currentPage]);

  /* ===== Действия по категориям ===== */

  const handleRegenerate = async (id) => {
    setRegeneratingIds((prev) => new Set(prev).add(id));
    try {
      const res = await fetch(`${API_BASE}/api/categories/${id}/regenerate`, {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      // подтягиваем свежую категорию
      const catResp = await fetch(`${API_BASE}/api/categories/${id}`);
      if (catResp.ok) {
        const { category } = await catResp.json();
        setCategories((prev) =>
          prev.map((c) => (c.id === id ? { ...c, ...category } : c))
        );
      }
    } catch (e) {
      console.error("Ошибка перегенерации", e);
      alert("Не удалось отправить запрос на перегенерацию");
    } finally {
      setRegeneratingIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleRatingChange = async (id, rating) => {
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, rating } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}/rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating }),
      });
    } catch (e) {
      console.error("Ошибка сохранения рейтинга", e);
      alert("Не удалось сохранить рейтинг категории");
    }
  };

  const handleCategoryUpdate = async (id, updates) => {
    setCategories((prev) =>
      prev.map((c) => (c.id === id ? { ...c, ...updates } : c))
    );

    try {
      await fetch(`${API_BASE}/api/categories/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
    } catch (e) {
      console.error("Ошибка сохранения изменений категории", e);
      alert("Не удалось сохранить изменения категории");
    }
  };

  /* ===== Модалка товаров (СТЕ) ===== */

  const fetchProductsForModal = async (categoryId, productIds) => {
    if (!productIds || productIds.length === 0) {
      setProductsModal((prev) =>
        prev && prev.id === categoryId
          ? { ...prev, loading: false, products: [] }
          : prev
      );
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/products/by-ids`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: productIds }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      const list = Array.isArray(data.products) ? data.products : data;
      setProductsModal((prev) =>
        prev && prev.id === categoryId
          ? { ...prev, loading: false, products: list }
          : prev
      );
    } catch (e) {
      console.error("Ошибка загрузки товаров", e);
      setProductsModal((prev) =>
        prev && prev.id === categoryId
          ? { ...prev, loading: false, error: "Не удалось загрузить товары" }
          : prev
      );
    }
  };

  const handleShowProductsModal = (category) => {
    if (!category) return;
    const { id, name, productIds } = category;
    setProductsModal({
      id,
      name,
      productIds: productIds || [],
      products: [],
      loading: true,
      error: "",
    });

    fetchProductsForModal(id, productIds || []);
  };

  const handleProductsRegenerateSelected = async (categoryId, ids) => {
    try {
      const body =
        Array.isArray(ids) && ids.length > 0
          ? { productIds: ids }
          : { all: true };
      const res = await fetch(
        `${API_BASE}/api/categories/${categoryId}/regenerate-products`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (e) {
      console.error("Ошибка перегенерации по товарам", e);
      alert("Не удалось отправить запрос на перегенерацию по товарам");
    }
  };

  /* ===== Умный поиск ===== */

  const handleSmartSearchChange = (e) => {
    const q = e.target.value;
    setSearch(q);
    setSmartError("");

    if (smartTimeoutRef.current) {
      clearTimeout(smartTimeoutRef.current);
      smartTimeoutRef.current = null;
    }

    if (!q.trim()) {
      setSmartLoading(false);
      setSmartResultIds([]);
      return;
    }

    smartTimeoutRef.current = setTimeout(async () => {
      try {
        setSmartLoading(true);
        const params = new URLSearchParams({ q });
        const res = await fetch(
          `${API_BASE}/api/search/categories?${params.toString()}`
        );
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json(); // [{id,name,score,...}]

        if (!Array.isArray(data) || data.length === 0) {
          setSmartError("Ничего не найдено");
          setSmartResultIds([]);
          return;
        }

        const ids = data.map((r) => r.id);
        setSmartResultIds(ids);
      } catch (e) {
        console.error("Ошибка умного поиска", e);
        setSmartError("Ошибка умного поиска");
        setSmartResultIds([]);
      } finally {
        setSmartLoading(false);
      }
    }, 500);
  };

  /* ===== Excel-фильтры в шапке таблицы категорий ===== */

  const toggleMainFilterValue = (kind, key, checked) => {
    if (kind === "status") {
      setStatusFilterValues((prev) => {
        const next = new Set(prev);
        if (checked) next.add(key);
        else next.delete(key);
        return next;
      });
    } else if (kind === "rating") {
      setRatingFilterValues((prev) => {
        const next = new Set(prev);
        if (checked) next.add(key);
        else next.delete(key);
        return next;
      });
    }
  };

  const selectAllMainFilterValues = (kind, options) => {
    const set = new Set(options);
    if (kind === "status") {
      setStatusFilterValues(set);
    } else if (kind === "rating") {
      setRatingFilterValues(set);
    }
  };

  const clearMainFilterValues = (kind) => {
    if (kind === "status") {
      setStatusFilterValues(new Set());
    } else if (kind === "rating") {
      setRatingFilterValues(new Set());
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="page-title">Категории товаров (TH3 Admin)</h1>
      </header>

      <main className="layout">
        {/* ЛЕВАЯ ПАНЕЛЬ */}
        <section className="panel-left">
          <div className="filters">
            <div className="filters-row">
              <div className="filter-item wide">
                <label>Поиск по категории (умный поиск)</label>
                <input
                  className="input"
                  placeholder="Введите текст…"
                  value={search}
                  onChange={handleSmartSearchChange}
                />
                {smartLoading && (
                  <div className="smart-search-indicator">Поиск…</div>
                )}
                {smartError && (
                  <div className="smart-search-error">{smartError}</div>
                )}
              </div>
            </div>

            <div className="filters-row">
              <div className="filter-item">
                <label>ID категории</label>
                <input
                  className="input"
                  placeholder="Например, 793286151"
                  value={filterId}
                  onChange={(e) => setFilterId(e.target.value)}
                />
              </div>

              <div className="filter-item">
                <label>Статус одобрения</label>
                <select
                  className="input"
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                >
                  <option value="all">Все</option>
                  <option value="pending">Не обработано</option>
                  <option value="approved">Одобрено</option>
                  <option value="rejected">Не одобрено</option>
                </select>
              </div>

              <div className="filter-item">
                <label>Дата с</label>
                <input
                  type="date"
                  className="input"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </div>

              <div className="filter-item">
                <label>Дата по</label>
                <input
                  type="date"
                  className="input"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="table-wrapper">
            {loading ? (
              <div className="table">
                <div className="table-empty">Загрузка категорий…</div>
              </div>
            ) : error ? (
              <div className="table">
                <div className="table-empty table-empty-error">{error}</div>
              </div>
            ) : (
              <>
                <table className="table">
                  <thead>
                    <tr>
                      <th>ID категории</th>
                      <th>Название категории</th>
                      <th>Описание</th>
                      <th>Дата генерации</th>
                      <th>Новые товары</th>
                      <th>
                        <div className="col-header-with-filter">
                          <span>Статус</span>
                          <button
                            type="button"
                            className={
                              statusFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setStatusFilterOpen((v) => !v);
                            }}
                          >
                            ▾
                          </button>

                          {statusFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по статусу
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAllMainFilterValues(
                                      "status",
                                      statusOptions
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    clearMainFilterValues("status")
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {statusOptions.map((key) => {
                                  const checked =
                                    statusFilterValues.has(key);
                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleMainFilterValue(
                                            "status",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{statusLabel(key)}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>

                      <th>
                        <div className="col-header-with-filter">
                          <span>Оценка</span>
                          <button
                            type="button"
                            className={
                              ratingFilterValues.size > 0
                                ? "col-filter-trigger col-filter-trigger--active"
                                : "col-filter-trigger"
                            }
                            onClick={(e) => {
                              e.stopPropagation();
                              setRatingFilterOpen((v) => !v);
                            }}
                          >
                            ▾
                          </button>

                          {ratingFilterOpen && (
                            <div className="col-filter-popover">
                              <div className="col-filter-popover-header">
                                Фильтр по оценке
                              </div>

                              <div className="col-filter-actions">
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    selectAllMainFilterValues(
                                      "rating",
                                      ratingOptions
                                    )
                                  }
                                >
                                  Выбрать все
                                </button>
                                <button
                                  type="button"
                                  className="col-filter-link"
                                  onClick={() =>
                                    clearMainFilterValues("rating")
                                  }
                                >
                                  Сбросить
                                </button>
                              </div>

                              <div className="col-filter-options">
                                {ratingOptions.map((key) => {
                                  const checked =
                                    ratingFilterValues.has(key);
                                  const num = Number(key);
                                  const label =
                                    num === 0 ? "Без оценки" : `${num} ★`;
                                  return (
                                    <label
                                      key={key}
                                      className="col-filter-option"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                          toggleMainFilterValue(
                                            "rating",
                                            key,
                                            e.target.checked
                                          )
                                        }
                                      />
                                      <span>{label}</span>
                                    </label>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCategories.length === 0 && (
                      <tr>
                        <td className="table-empty" colSpan={7}>
                          Нет категорий, подходящих под фильтр
                        </td>
                      </tr>
                    )}

                    {paginatedCategories.map((cat) => (
                      <tr
                        key={cat.id}
                        className={
                          "table-row" +
                          (cat.id === selectedCategoryId
                            ? " table-row--active"
                            : "") +
                          (cat.hasUntrainedItems
                            ? " table-row--warning"
                            : "")
                        }
                        onClick={() => setSelectedCategoryId(cat.id)}
                      >
                        <td>{cat.id}</td>
                        <td className="table-cell-name">{cat.name}</td>
                        <td className="table-cell-description">
                          {cat.description || "—"}
                        </td>
                        <td>{formatDate(cat.generatedAt || cat.createdAt)}</td>
                        <td>
                          {cat.hasNewItems ? (
                            <span className="new-items-badge">
                              Есть новые ({cat.newItemsCount ?? 0})
                            </span>
                          ) : (
                            <span className="new-items-badge new-items-badge--none">
                              Нет
                            </span>
                          )}

                          {cat.hasUntrainedItems && (
                            <div className="training-warning">
                              Необученных СТЕ: {cat.untrainedItemsCount}
                            </div>
                          )}
                        </td>

                        <td>
                          <span
                            className={`status-badge ${
                              cat.status === "approved"
                                ? "status-badge--approved"
                                : cat.status === "rejected"
                                ? "status-badge--rejected"
                                : "status-badge--pending"
                            }`}
                          >
                            {statusLabel(cat.status)}
                          </span>
                        </td>
                        <td>
                          <StarRating
                            value={cat.rating ?? 0}
                            onChange={(v) => handleRatingChange(cat.id, v)}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="pagination">
                  <button
                    type="button"
                    className="btn btn-ghost btn-small"
                    disabled={currentPage === 1}
                    onClick={() =>
                      setCurrentPage((p) => Math.max(1, p - 1))
                    }
                  >
                    ◀
                  </button>
                  <span className="pagination-info">
                    Страница {currentPage} из {totalPages}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost btn-small"
                    disabled={currentPage === totalPages}
                    onClick={() =>
                      setCurrentPage((p) =>
                        Math.min(totalPages, p + 1)
                      )
                    }
                  >
                    ▶
                  </button>
                </div>
              </>
            )}
          </div>
        </section>

        {/* ПРАВАЯ ПАНЕЛЬ */}
        <section className="panel-right">
          {selectedCategory ? (
            <CategoryCard
              category={selectedCategory}
              onRegenerate={handleRegenerate}
              onRatingChange={handleRatingChange}
              onUpdateCategory={handleCategoryUpdate}
              onShowProducts={() => handleShowProductsModal(selectedCategory)}
              isRegenerating={regeneratingIds.has(selectedCategory.id)}
            />
          ) : (
            <div className="card-empty">
              Выберите категорию слева, чтобы посмотреть детали
            </div>
          )}
        </section>
      </main>

      {productsModal && (
        <ProductsModal
          data={productsModal}
          onClose={() => setProductsModal(null)}
          onRegenerateSelected={handleProductsRegenerateSelected}
        />
      )}
    </div>
  );
}

export default App;
