(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  const React = SDK.React;
  const hooks = SDK.hooks;
  const C = SDK.components;
  const cn = SDK.utils.cn;

  const rarityClass = function (rarity) {
    return "ha-rarity-" + String(rarity || "common").toLowerCase().replace(/\s+/g, "-");
  };
  const tierClass = function (tier) {
    return tier ? "ha-tier-" + tier.toLowerCase() : "ha-tier-locked";
  };

  function api(path, options) {
    return SDK.fetchJSON("/api/plugins/hermes-achievements" + path, options);
  }

  function StatCard(props) {
    return React.createElement(C.Card, { className: "ha-stat" },
      React.createElement(C.CardContent, { className: "ha-stat-content" },
        React.createElement("div", { className: "ha-stat-label" }, props.label),
        React.createElement("div", { className: "ha-stat-value" }, props.value),
        props.hint && React.createElement("div", { className: "ha-stat-hint" }, props.hint)
      )
    );
  }

  function AchievementCard({ achievement }) {
    const unlocked = achievement.unlocked;
    const progress = achievement.progress || 0;
    const pct = achievement.progress_pct || (unlocked ? 100 : 0);
    const state = achievement.state || (unlocked ? "unlocked" : "locked");
    const medal = state === "unlocked" ? "★" : state === "discovered" ? "◇" : "?";
    return React.createElement(C.Card, { className: cn("ha-card", "ha-state-" + state, unlocked ? "ha-unlocked" : "ha-locked", rarityClass(achievement.rarity), tierClass(achievement.tier)) },
      React.createElement(C.CardContent, { className: "ha-card-content" },
        React.createElement("div", { className: "ha-card-top" },
          React.createElement("div", { className: "ha-medal" }, medal),
          React.createElement("div", { className: "ha-card-title-wrap" },
            React.createElement("div", { className: "ha-card-title" }, achievement.name),
            React.createElement("div", { className: "ha-card-category" }, achievement.category)
          ),
          React.createElement("div", { className: "ha-badges" },
            React.createElement("span", { className: "ha-rarity-badge" }, achievement.rarity),
            React.createElement("span", { className: "ha-state-badge" }, state),
            React.createElement("span", { className: "ha-tier-badge" }, achievement.tier || (state === "discovered" ? "Progress" : "Locked"))
          )
        ),
        React.createElement("p", { className: "ha-description" }, achievement.description),
        React.createElement("div", { className: "ha-progress-row" },
          React.createElement("div", { className: "ha-progress-track" },
            React.createElement("div", { className: "ha-progress-fill", style: { width: Math.max(3, Math.min(100, pct)) + "%" } })
          ),
          React.createElement("span", { className: "ha-progress-text" }, progress, achievement.next_threshold ? " / " + achievement.next_threshold : "")
        ),
        achievement.evidence && React.createElement("div", { className: "ha-evidence" },
          React.createElement("span", null, "Evidence: "),
          React.createElement("code", null, achievement.evidence.title || achievement.evidence.session_id || "session")
        )
      )
    );
  }

  function AchievementsPage() {
    const [data, setData] = hooks.useState(null);
    const [loading, setLoading] = hooks.useState(true);
    const [error, setError] = hooks.useState(null);
    const [category, setCategory] = hooks.useState("All");
    const [visibility, setVisibility] = hooks.useState("all");

    function load() {
      setLoading(true);
      api("/achievements")
        .then(function (payload) { setData(payload); setError(payload.error || null); })
        .catch(function (err) { setError(String(err)); })
        .finally(function () { setLoading(false); });
    }
    hooks.useEffect(load, []);

    const achievements = (data && data.achievements) || [];
    const categories = ["All"].concat(Array.from(new Set(achievements.map(function (a) { return a.category; }))));
    const visible = achievements.filter(function (a) {
      if (category !== "All" && a.category !== category) return false;
      if (visibility === "unlocked" && a.state !== "unlocked") return false;
      if (visibility === "discovered" && a.state !== "discovered") return false;
      if (visibility === "secret" && a.state !== "secret") return false;
      if (visibility === "locked" && a.state !== "locked") return false;
      return true;
    });
    const unlocked = achievements.filter(function (a) { return a.state === "unlocked"; });
    const discovered = achievements.filter(function (a) { return a.state === "discovered"; });
    const secret = achievements.filter(function (a) { return a.state === "secret"; });
    const latest = unlocked.slice().sort(function (a, b) { return (b.unlocked_at || 0) - (a.unlocked_at || 0); }).slice(0, 5);
    const highest = ["Olympian", "Diamond", "Gold", "Silver", "Copper"].find(function (tier) { return unlocked.some(function (a) { return a.tier === tier; }); }) || "None yet";

    if (loading) {
      return React.createElement("div", { className: "ha-page" }, React.createElement("div", { className: "ha-loading" }, "Scanning Hermes sessions…"));
    }

    return React.createElement("div", { className: "ha-page" },
      React.createElement("section", { className: "ha-hero" },
        React.createElement("div", null,
          React.createElement("div", { className: "ha-kicker" }, "Agentic Gamerscore"),
          React.createElement("h1", null, "Hermes Achievements"),
          React.createElement("p", null, "Steam-style badges for vibe coding, autonomous tool chains, debugging chaos, and Hermes-native workflows.")
        ),
        React.createElement(C.Button, { onClick: load, className: "ha-refresh" }, "Rescan")
      ),
      error && React.createElement(C.Card, { className: "ha-error" }, React.createElement(C.CardContent, null, String(error))),
      React.createElement("div", { className: "ha-stats" },
        React.createElement(StatCard, { label: "Unlocked", value: (data ? data.unlocked_count : 0) + " / " + (data ? data.total_count : 0), hint: "earned badges" }),
        React.createElement(StatCard, { label: "Discovered", value: discovered.length, hint: "progress started" }),
        React.createElement(StatCard, { label: "Secrets", value: secret.length, hint: "still hidden" }),
        React.createElement(StatCard, { label: "Highest tier", value: highest, hint: "Copper → Olympian" }),
        React.createElement(StatCard, { label: "Latest", value: latest[0] ? latest[0].name : "None yet", hint: latest[0] ? latest[0].rarity : "run Hermes more" })
      ),
      React.createElement("div", { className: "ha-toolbar" },
        React.createElement("div", { className: "ha-pills" }, categories.map(function (cat) {
          return React.createElement("button", { key: cat, onClick: function () { setCategory(cat); }, className: cat === category ? "active" : "" }, cat);
        })),
        React.createElement("div", { className: "ha-pills" }, ["all", "unlocked", "discovered", "secret", "locked"].map(function (v) {
          return React.createElement("button", { key: v, onClick: function () { setVisibility(v); }, className: v === visibility ? "active" : "" }, v);
        }))
      ),
      latest.length > 0 && React.createElement("section", { className: "ha-latest" },
        React.createElement("h2", null, "Recent unlocks"),
        React.createElement("div", { className: "ha-latest-row" }, latest.map(function (a) {
          return React.createElement("div", { key: a.id, className: cn("ha-chip", rarityClass(a.rarity)) }, "★ ", a.name);
        }))
      ),
      React.createElement("section", { className: "ha-grid" }, visible.map(function (a) {
        return React.createElement(AchievementCard, { key: a.id, achievement: a });
      }))
    );
  }

  function SummarySlot({ compact }) {
    const [overview, setOverview] = hooks.useState(null);
    hooks.useEffect(function () { api("/overview").then(setOverview).catch(function () {}); }, []);
    if (!overview) return null;
    return React.createElement(C.Card, { className: "ha-slot" },
      React.createElement(C.CardContent, { className: "ha-slot-content" },
        React.createElement("span", { className: "ha-slot-star" }, "★"),
        React.createElement("span", null, "Hermes Achievements: ", React.createElement("strong", null, overview.unlocked_count, " / ", overview.total_count), " unlocked"),
        !compact && overview.latest && overview.latest[0] && React.createElement("span", { className: "ha-slot-muted" }, "Latest: " + overview.latest[0].name)
      )
    );
  }

  window.__HERMES_PLUGINS__.register("hermes-achievements", AchievementsPage);
  window.__HERMES_PLUGINS__.registerSlot("hermes-achievements", "sessions:top", function () { return React.createElement(SummarySlot, { compact: false }); });
  window.__HERMES_PLUGINS__.registerSlot("hermes-achievements", "analytics:top", function () { return React.createElement(SummarySlot, { compact: true }); });
})();
