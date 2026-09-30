/* Review workspace: tabbed tables over the Phase 1 list/detail API. */
(function () {
  'use strict';

  var TABS = {
    claims: {
      label: 'Claims',
      endpoint: '/api/claims/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'claim_type', label: 'Type', sortable: true },
        { key: 'evidence_excerpt', label: 'Evidence', excerpt: true },
        { key: 'source_label', label: 'Source' },
        { key: 'section', label: 'Section', sortable: true },
        { key: 'status', label: 'Status', sortable: true, badge: true },
        { key: 'created', label: 'Created', sortable: true, mono: true }
      ],
      filters: [
        { name: 'status', label: 'Status', type: 'select', options: ['', 'pending', 'approved', 'rejected'] },
        { name: 'claim_type', label: 'Type', type: 'text' },
        { name: 'trial', label: 'Trial ID', type: 'text' },
        { name: 'publication', label: 'Publication ID', type: 'text' },
        { name: 'disease', label: 'Disease ID', type: 'text' },
        { name: 'intervention', label: 'Intervention ID', type: 'text' }
      ]
    },
    diseases: {
      label: 'Diseases',
      endpoint: '/api/diseases/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'name', label: 'Name', sortable: true },
        { key: 'mesh', label: 'MeSH', sortable: true, mono: true },
        { key: 'created', label: 'Created', sortable: true, mono: true }
      ],
      filters: [{ name: 'mesh', label: 'MeSH', type: 'text' }]
    },
    interventions: {
      label: 'Interventions',
      endpoint: '/api/interventions/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'name', label: 'Name', sortable: true },
        { key: 'mesh', label: 'MeSH', sortable: true, mono: true },
        { key: 'created', label: 'Created', sortable: true, mono: true }
      ],
      filters: [{ name: 'mesh', label: 'MeSH', type: 'text' }]
    },
    trials: {
      label: 'Trials',
      endpoint: '/api/trials/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'nct_id', label: 'NCT ID', sortable: true, mono: true },
        { key: 'title', label: 'Title', sortable: true, excerpt: true },
        { key: 'status', label: 'Status', sortable: true },
        { key: 'phase', label: 'Phase', sortable: true },
        { key: 'start_date', label: 'Start', sortable: true, mono: true }
      ],
      filters: [
        { name: 'status', label: 'Status', type: 'text' },
        { name: 'phase', label: 'Phase', type: 'text' },
        { name: 'has_results', label: 'Has results', type: 'select', options: ['', 'true', 'false'] },
        { name: 'publication', label: 'Publication ID', type: 'text' }
      ]
    },
    publications: {
      label: 'Publications',
      endpoint: '/api/publications/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'pmid', label: 'PMID', sortable: true, mono: true },
        { key: 'title', label: 'Title', sortable: true, excerpt: true },
        { key: 'journal', label: 'Journal', sortable: true },
        { key: 'year', label: 'Year', sortable: true, numeric: true },
        { key: 'pub_date', label: 'Date', sortable: true, mono: true }
      ],
      filters: [
        { name: 'year', label: 'Year', type: 'text' },
        { name: 'journal', label: 'Journal', type: 'text' },
        { name: 'trial', label: 'Trial ID', type: 'text' }
      ]
    }
  };

  var state = {
    tab: 'claims',
    search: '',
    filters: {},
    ordering: null,
    page: 1,
    selected: null,
    controller: null,
    seq: 0
  };

  var els = {};

  function text(parent, value, tag, className) {
    var node = document.createElement(tag || 'span');
    if (className) {
      node.setAttribute('class', className);
    }
    node.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
    parent.appendChild(node);
    return node;
  }

  function clear(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function csrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  }

  function currentConfig() {
    return TABS[state.tab];
  }

  function orderingParam() {
    if (!state.ordering) {
      return null;
    }
    var field = state.ordering;
    var base = field.charAt(0) === '-' ? field.slice(1) : field;
    var tie = field.charAt(0) === '-' ? '-id' : 'id';
    if (base === 'id') {
      return field;
    }
    return field + ',' + tie;
  }

  function buildListUrl(page) {
    var params = new URLSearchParams();
    if (state.search) {
      params.set('search', state.search);
    }
    Object.keys(state.filters).forEach(function (name) {
      if (state.filters[name] !== '') {
        params.set(name, state.filters[name]);
      }
    });
    var ordering = orderingParam();
    if (ordering) {
      params.set('ordering', ordering);
    }
    params.set('page', String(page || state.page));
    return currentConfig().endpoint + '?' + params.toString();
  }

  function setStatus(message, isError) {
    clear(els.status);
    els.status.textContent = message || '';
    els.status.setAttribute('class', isError ? 'ws-status is-error' : 'ws-status');
  }

  function setCount(first, last, total) {
    clear(els.count);
    if (total === null || total === undefined) {
      els.count.textContent = '';
      return;
    }
    if (!total) {
      els.count.textContent = '0 records';
      return;
    }
    els.count.textContent = first + '–' + last + ' of ' + total;
  }

  function renderHead() {
    clear(els.thead);
    var config = currentConfig();
    var tr = document.createElement('tr');
    config.columns.forEach(function (col, index) {
      var th = document.createElement('th');
      if (col.numeric) {
        th.setAttribute('class', 'num');
      }
      if (col.sortable) {
        var btn = document.createElement('button');
        btn.setAttribute('type', 'button');
        btn.setAttribute('class', 'ws-sort');
        btn.setAttribute('data-field', col.key);
        var arrow = '';
        if (state.ordering === col.key) {
          arrow = ' ▲';
        } else if (state.ordering === '-' + col.key) {
          arrow = ' ▼';
        }
        btn.textContent = col.label + arrow;
        btn.addEventListener('click', function () {
          if (state.ordering === col.key) {
            state.ordering = '-' + col.key;
          } else if (state.ordering === '-' + col.key) {
            state.ordering = null;
          } else {
            state.ordering = col.key;
          }
          state.page = 1;
          loadList();
        });
        th.appendChild(btn);
      } else {
        th.textContent = col.label;
      }
      if (index === 0) {
        th.setAttribute('scope', 'col');
      }
      tr.appendChild(th);
    });
    els.thead.appendChild(tr);
  }

  function cellValue(row, col) {
    var value = row[col.key];
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return value;
  }

  function renderRows(results) {
    clear(els.tbody);
    var config = currentConfig();
    results.forEach(function (row) {
      var tr = document.createElement('tr');
      if (state.selected && state.selected.tab === state.tab && state.selected.id === row.id) {
        tr.setAttribute('class', 'is-selected');
      }
      tr.addEventListener('click', function () {
        selectRow(row.id);
      });
      config.columns.forEach(function (col, index) {
        var td = document.createElement('td');
        var classes = [];
        if (col.numeric) {
          classes.push('num');
        }
        if (col.mono) {
          classes.push('mono');
        }
        if (col.excerpt) {
          classes.push('ws-excerpt');
        }
        if (classes.length) {
          td.setAttribute('class', classes.join(' '));
        }
        var value = cellValue(row, col);
        if (col.badge && value !== null) {
          var badge = document.createElement('span');
          badge.setAttribute('class', 'badge badge-' + String(value));
          badge.textContent = String(value);
          td.appendChild(badge);
        } else if (index === 0) {
          var open = document.createElement('button');
          open.setAttribute('type', 'button');
          open.setAttribute('class', 'ws-row-open mono');
          open.setAttribute('aria-label', 'Open ' + config.label + ' ' + String(value));
          open.textContent = value === null ? '—' : String(value);
          open.addEventListener('click', function (event) {
            event.stopPropagation();
            selectRow(row.id);
          });
          td.appendChild(open);
        } else {
          td.textContent = value === null ? '—' : String(value);
          if (value === null) {
            td.setAttribute('class', (td.getAttribute('class') || '') + ' ws-empty-cell');
          }
        }
        tr.appendChild(td);
      });
      els.tbody.appendChild(tr);
    });
  }

  function renderFilters() {
    clear(els.filters);
    var config = currentConfig();
    config.filters.forEach(function (filter) {
      var label = document.createElement('label');
      label.setAttribute('class', 'ws-filter');
      var caption = document.createElement('span');
      caption.textContent = filter.label;
      label.appendChild(caption);
      var control;
      if (filter.type === 'select') {
        control = document.createElement('select');
        control.setAttribute('class', 'ws-filter-select');
        filter.options.forEach(function (option) {
          var opt = document.createElement('option');
          opt.value = option;
          opt.textContent = option === '' ? 'Any' : option;
          control.appendChild(opt);
        });
      } else {
        control = document.createElement('input');
        control.setAttribute('type', 'text');
        control.setAttribute('class', 'ws-filter-input');
      }
      control.setAttribute('name', filter.name);
      control.setAttribute('aria-label', filter.label);
      control.value = state.filters[filter.name] || '';
      control.addEventListener('change', function () {
        state.filters[filter.name] = control.value;
        state.page = 1;
        state.selected = null;
        renderPrompt();
        loadList();
      });
      label.appendChild(control);
    });
  }

  function renderTabs() {
    var buttons = els.tabs.querySelectorAll('[data-tab]');
    buttons.forEach(function (btn) {
      btn.setAttribute('aria-selected', btn.getAttribute('data-tab') === state.tab ? 'true' : 'false');
    });
  }

  function renderPrompt() {
    clear(els.detail);
    var prompt = document.createElement('p');
    prompt.setAttribute('class', 'ws-prompt');
    prompt.textContent = 'Select a row above to review its details.';
    els.detail.appendChild(prompt);
  }

  function renderDetailLoading(id) {
    clear(els.detail);
    var prompt = document.createElement('p');
    prompt.setAttribute('class', 'ws-prompt');
    prompt.textContent = 'Loading ' + currentConfig().label + ' ' + String(id) + '…';
    els.detail.appendChild(prompt);
  }

  function selectRow(id) {
    state.selected = { tab: state.tab, id: id };
    renderDetailLoading(id);
    loadList({ keepSelection: true });
    // Full detail renderers arrive with the lower-pane task.
    fetch(currentConfig().endpoint + id + '/', { headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Detail request failed: ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (!state.selected || state.selected.id !== id || state.selected.tab !== state.tab) {
          return;
        }
        renderDetail(data);
      })
      .catch(function () {
        if (!state.selected || state.selected.id !== id) {
          return;
        }
        clear(els.detail);
        var prompt = document.createElement('p');
        prompt.setAttribute('class', 'ws-prompt');
        prompt.textContent = 'Could not load details. Select the row again to retry.';
        els.detail.appendChild(prompt);
      });
  }

  function renderDetail(data) {
    // Placeholder until the lower-pane task implements per-model renderers.
    clear(els.detail);
    var heading = document.createElement('h2');
    heading.textContent = currentConfig().label + ' ' + String(data.id);
    els.detail.appendChild(heading);
    var prompt = document.createElement('p');
    prompt.setAttribute('class', 'ws-prompt');
    prompt.textContent = 'Full details arrive with the lower-pane task.';
    els.detail.appendChild(prompt);
  }

  function loadList(options) {
    var config = currentConfig();
    renderHead();
    renderTabs();
    if (state.controller) {
      state.controller.abort();
    }
    var controller = new AbortController();
    state.controller = controller;
    var seq = state.seq + 1;
    state.seq = seq;
    setStatus('Loading…', false);
    fetch(buildListUrl(), { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (response.status === 404) {
          var err = new Error('Page out of range.');
          err.outOfRange = true;
          throw err;
        }
        if (!response.ok) {
          throw new Error('List request failed: ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (seq !== state.seq || config !== currentConfig()) {
          return;
        }
        var results = data.results || [];
        renderRows(results);
        var total = data.count || 0;
        var pageSize = results.length;
        var first = total ? (state.page - 1) * 25 + 1 : 0;
        setCount(first, first + pageSize - 1, total);
        els.prev.disabled = !data.previous;
        els.next.disabled = !data.next;
        if (!results.length) {
          setStatus(total ? 'Page out of range.' : 'No records found.', false);
        } else {
          setStatus('', false);
        }
        if (!options || !options.keepSelection) {
          // Selection highlight refreshes through renderRows.
        }
      })
      .catch(function (err) {
        if (err && err.name === 'AbortError') {
          return;
        }
        if (seq !== state.seq || config !== currentConfig()) {
          return;
        }
        clear(els.tbody);
        setCount(0, 0, 0);
        els.prev.disabled = true;
        els.next.disabled = true;
        setStatus(err && err.outOfRange ? 'Page out of range.' : 'Could not load records.', true);
      });
  }

  function switchTab(tab) {
    if (!TABS[tab] || tab === state.tab) {
      if (TABS[tab]) {
        state.search = '';
        els.search.value = '';
        state.filters = {};
        state.ordering = null;
        state.page = 1;
        state.selected = null;
        renderFilters();
        renderPrompt();
        loadList();
      }
      return;
    }
    state.tab = tab;
    state.search = '';
    els.search.value = '';
    state.filters = {};
    state.ordering = null;
    state.page = 1;
    state.selected = null;
    renderFilters();
    renderPrompt();
    loadList();
  }

  function init() {
    els.tabs = document.querySelector('.ws-tabs');
    els.search = document.getElementById('ws-search');
    els.filters = document.getElementById('ws-filters');
    els.thead = document.getElementById('ws-thead');
    els.tbody = document.getElementById('ws-tbody');
    els.count = document.getElementById('ws-count');
    els.prev = document.getElementById('ws-prev');
    els.next = document.getElementById('ws-next');
    els.status = document.getElementById('ws-status');
    els.detail = document.getElementById('ws-detail');
    els.modal = document.getElementById('ws-modal');
    els.modalTitle = document.getElementById('ws-modal-title');
    els.modalBody = document.getElementById('ws-modal-body');
    els.modalClose = document.getElementById('ws-modal-close');

    els.tabs.addEventListener('click', function (event) {
      var btn = event.target.closest('[data-tab]');
      if (btn) {
        switchTab(btn.getAttribute('data-tab'));
      }
    });

    var debounce = null;
    els.search.addEventListener('input', function () {
      if (debounce) {
        window.clearTimeout(debounce);
      }
      debounce = window.setTimeout(function () {
        state.search = els.search.value;
        state.page = 1;
        state.selected = null;
        renderPrompt();
        loadList();
      }, 250);
    });

    els.prev.addEventListener('click', function () {
      if (state.page > 1) {
        state.page -= 1;
        loadList();
      }
    });
    els.next.addEventListener('click', function () {
      state.page += 1;
      loadList();
    });

    els.modalClose.addEventListener('click', function () {
      els.modal.close();
    });

    renderFilters();
    renderPrompt();
    loadList();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Exposed for the lower-pane task and browser checks.
  window.workspace = {
    state: state,
    csrfToken: csrfToken,
    switchTab: switchTab,
    selectRow: selectRow
  };
})();
