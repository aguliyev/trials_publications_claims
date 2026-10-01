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

  var MAIN_KINDS = {
    claims: '/api/claims/',
    diseases: '/api/diseases/',
    interventions: '/api/interventions/',
    trials: '/api/trials/',
    publications: '/api/publications/'
  };

  var RECORD_KINDS = {
    chunks: '/api/records/chunks/',
    ners: '/api/records/ners/',
    judgements: '/api/records/judgements/',
    biomarkers: '/api/records/biomarkers/',
    observations: '/api/records/observations/',
    'publication-trials': '/api/records/publication-trials/'
  };

  var KIND_LABELS = {
    claims: 'Claim',
    diseases: 'Disease',
    interventions: 'Intervention',
    trials: 'Trial',
    publications: 'Publication',
    chunks: 'Chunk',
    ners: 'Named entity',
    judgements: 'Judgement',
    biomarkers: 'Biomarker',
    observations: 'Observation',
    'publication-trials': 'Publication–trial link'
  };

  var FK_KINDS = {
    claim: 'claims',
    trial: 'trials',
    publication: 'publications',
    chunk: 'chunks',
    disease: 'diseases',
    intervention: 'interventions',
    ner: 'ners',
    judgement: 'judgements',
    biomarker: 'biomarkers',
    observation: 'observations'
  };

  var CLAIM_STATUSES = ['pending', 'approved', 'rejected'];

  var RELATED_CLAIM_COLUMNS = [
    { key: 'id', label: 'ID', numeric: true },
    { key: 'claim_type', label: 'Type' },
    { key: 'evidence_excerpt', label: 'Evidence', excerpt: true },
    { key: 'section', label: 'Section' },
    { key: 'status', label: 'Status', badge: true }
  ];

  var state = {
    tab: 'claims',
    search: '',
    filters: {},
    ordering: null,
    page: 1,
    selected: null,
    detail: null,
    controller: null,
    seq: 0
  };

  var els = {};
  var modalOpener = null;
  var operation = null;

  function make(tag, className, value) {
    var node = document.createElement(tag);
    if (className) {
      node.setAttribute('class', className);
    }
    if (value !== undefined) {
      node.textContent = value === null || value === '' ? '—' : String(value);
    }
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

  function kindLabel(kind) {
    return KIND_LABELS[kind] || kind;
  }

  function recordUrl(kind, id) {
    if (MAIN_KINDS[kind]) {
      return MAIN_KINDS[kind] + id + '/';
    }
    if (RECORD_KINDS[kind]) {
      return RECORD_KINDS[kind] + id + '/';
    }
    return null;
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
    if (!total || !first) {
      els.count.textContent = String(total || 0) + ' records';
      return;
    }
    els.count.textContent = first + '–' + last + ' of ' + total;
  }

  function badgeCell(value) {
    var badge = document.createElement('span');
    badge.setAttribute('class', 'badge badge-' + String(value));
    badge.textContent = String(value);
    return badge;
  }

  function openButton(label, kind, id) {
    var btn = document.createElement('button');
    btn.setAttribute('type', 'button');
    btn.setAttribute('class', 'ws-row-open mono');
    btn.textContent = label;
    btn.addEventListener('click', function (event) {
      event.stopPropagation();
      openRecord(kind, id);
    });
    return btn;
  }

  /* ---------- Upper table ---------- */

  function renderHead() {
    clear(els.thead);
    var config = currentConfig();
    var tr = document.createElement('tr');
    config.columns.forEach(function (col, index) {
      var th = document.createElement('th');
      if (col.numeric) {
        th.setAttribute('class', 'num');
      }
      if (index === 0) {
        th.setAttribute('scope', 'col');
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
          td.appendChild(badgeCell(value));
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
        state.detail = null;
        renderPrompt();
        loadList();
      });
      label.appendChild(control);
      els.filters.appendChild(label);
    });
  }

  function renderTabs() {
    var buttons = els.tabs.querySelectorAll('[data-tab]');
    buttons.forEach(function (btn) {
      btn.setAttribute('aria-selected', btn.getAttribute('data-tab') === state.tab ? 'true' : 'false');
    });
  }

  function renderImportForms() {
    els.importTrials.hidden = state.tab !== 'trials';
    els.importPublications.hidden = state.tab !== 'publications';
  }

  function renderPrompt() {
    clear(els.detail);
    els.detail.appendChild(make('p', 'ws-prompt', 'Select a row above to review its details.'));
  }

  function renderDetailLoading(id) {
    clear(els.detail);
    els.detail.appendChild(make('p', 'ws-prompt', 'Loading ' + currentConfig().label + ' ' + String(id) + '…'));
  }

  function selectRow(id) {
    state.selected = { tab: state.tab, id: id };
    renderDetailLoading(id);
    loadList({ keepSelection: true });
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
        state.detail = { tab: state.tab, id: id, data: data };
        renderDetail(state.tab, data);
      })
      .catch(function () {
        if (!state.selected || state.selected.id !== id) {
          return;
        }
        state.detail = null;
        clear(els.detail);
        els.detail.appendChild(make('p', 'ws-prompt', 'Could not load details. Select the row again to retry.'));
      });
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
        if (!results.length) {
          setCount(0, 0, total);
        } else {
          var first = (state.page - 1) * 25 + 1;
          setCount(first, first + results.length - 1, total);
        }
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
    if (!TABS[tab]) {
      return;
    }
    state.tab = tab;
    state.search = '';
    els.search.value = '';
    state.filters = {};
    state.ordering = null;
    state.page = 1;
    state.selected = null;
    state.detail = null;
    renderImportForms();
    renderFilters();
    renderPrompt();
    loadList();
  }

  /* ---------- Lower details ---------- */

  function fieldList(entries) {
    var dl = document.createElement('dl');
    dl.setAttribute('class', 'ws-fields');
    entries.forEach(function (entry) {
      var dt = document.createElement('dt');
      dt.textContent = entry[0];
      var dd = document.createElement('dd');
      var value = entry[1];
      if (value !== null && typeof value === 'object' && value.kind && value.id !== undefined) {
        dd.appendChild(openButton(value.label || (kindLabel(value.kind) + ' ' + String(value.id)), value.kind, value.id));
      } else if (entry[2] === 'badge' && value !== null && value !== '') {
        dd.appendChild(badgeCell(value));
      } else if (value === null || value === undefined || value === '') {
        dd.textContent = '—';
      } else {
        dd.textContent = String(value);
        if (entry[2] === 'mono') {
          dd.setAttribute('class', 'mono');
        }
      }
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    return dl;
  }

  function fkLink(kind, id, fallback) {
    if (id === null || id === undefined) {
      return null;
    }
    return { kind: kind, id: id, label: fallback || (kindLabel(kind) + ' ' + String(id)) };
  }

  function sectionHeading(value) {
    return make('h3', null, value);
  }

  function emptyNote(value) {
    return make('p', 'ws-prompt', value);
  }

  function relatedTable(columns, rows, emptyMessage) {
    var wrap = document.createElement('div');
    wrap.setAttribute('class', 'ws-table-wrap');
    if (!rows.length) {
      wrap.appendChild(emptyNote(emptyMessage));
      return wrap;
    }
    var table = document.createElement('table');
    table.setAttribute('class', 'ws-table');
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    columns.forEach(function (col) {
      var th = document.createElement('th');
      th.textContent = col.label;
      if (col.numeric) {
        th.setAttribute('class', 'num');
      }
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = document.createElement('tbody');
    rows.forEach(function (row) {
      var tr = document.createElement('tr');
      tr.addEventListener('click', function () {
        openRecord(row._kind, row._id);
      });
      columns.forEach(function (col, index) {
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
        var value = row[col.key];
        if (col.badge && value !== null && value !== undefined && value !== '') {
          td.appendChild(badgeCell(value));
        } else if (index === 0) {
          var btn = document.createElement('button');
          btn.setAttribute('type', 'button');
          btn.setAttribute('class', 'ws-row-open' + (col.mono ? ' mono' : ''));
          btn.setAttribute('aria-label', 'Open ' + kindLabel(row._kind) + ' ' + String(row._id));
          btn.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
          btn.addEventListener('click', function (event) {
            event.stopPropagation();
            openRecord(row._kind, row._id);
          });
          td.appendChild(btn);
        } else {
          td.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
        }
        if (classes.length) {
          td.setAttribute('class', classes.join(' '));
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function pagedRelatedTable(container, title, url, emptyMessage) {
    container.appendChild(sectionHeading(title));
    var holder = document.createElement('div');
    container.appendChild(holder);
    var page = 1;
    function load() {
      clear(holder);
      holder.appendChild(make('p', 'ws-prompt', 'Loading…'));
      fetch(url + (url.indexOf('?') === -1 ? '?' : '&') + 'page=' + page, { headers: { Accept: 'application/json' } })
        .then(function (response) {
          if (!response.ok) {
            throw new Error('Related request failed: ' + response.status);
          }
          return response.json();
        })
        .then(function (data) {
          clear(holder);
          var rows = (data.results || []).map(function (row) {
            row._kind = 'claims';
            row._id = row.id;
            return row;
          });
          holder.appendChild(relatedTable(RELATED_CLAIM_COLUMNS, rows, emptyMessage));
          var pager = document.createElement('div');
          pager.setAttribute('class', 'ws-related-pager');
          var prev = document.createElement('button');
          prev.setAttribute('type', 'button');
          prev.setAttribute('class', 'ws-btn');
          prev.textContent = 'Previous';
          prev.disabled = !data.previous;
          prev.addEventListener('click', function () {
            page -= 1;
            load();
          });
          var next = document.createElement('button');
          next.setAttribute('type', 'button');
          next.setAttribute('class', 'ws-btn');
          next.textContent = 'Next';
          next.disabled = !data.next;
          next.addEventListener('click', function () {
            page += 1;
            load();
          });
          pager.appendChild(prev);
          pager.appendChild(next);
          var count = make('span', null, (data.count || 0) + ' claim(s)');
          pager.appendChild(count);
          holder.appendChild(pager);
        })
        .catch(function () {
          clear(holder);
          holder.appendChild(make('p', 'ws-prompt', 'Could not load related claims.'));
        });
    }
    load();
  }

  function judgementBox(judgements) {
    var box = document.createElement('div');
    box.setAttribute('class', 'ws-judge');
    box.appendChild(sectionHeading('Judgements'));
    if (!judgements || !judgements.length) {
      box.appendChild(make('p', 'ws-prompt', 'No judgement'));
      return box;
    }
    var list = document.createElement('ul');
    judgements.forEach(function (judgement) {
      var item = document.createElement('li');
      var line = judgement.method + ' — score ' + String(judgement.score);
      if (judgement.meta && typeof judgement.meta === 'object' && judgement.meta.verdict) {
        line += ' · verdict: ' + String(judgement.meta.verdict);
      }
      item.textContent = line;
      if (judgement.meta && typeof judgement.meta === 'object' && !judgement.meta.verdict) {
        var meta = document.createElement('pre');
        meta.setAttribute('class', 'ws-json mono');
        meta.textContent = JSON.stringify(judgement.meta, null, 2);
        item.appendChild(meta);
      }
      list.appendChild(item);
    });
    box.appendChild(list);
    return box;
  }

  function sourceBlock(sectionText) {
    if (!sectionText) {
      return emptyNote('Source unavailable or ambiguous');
    }
    var wrap = document.createElement('div');
    var caption = make(
      'p',
      'ws-prompt mono',
      'Source: ' + sectionText.kind + ' ' + String(sectionText.id) + ' · section ' + sectionText.section
    );
    wrap.appendChild(caption);
    var body = make('p', 'ws-source-text', sectionText.text === null || sectionText.text === undefined || sectionText.text === '' ? '—' : String(sectionText.text));
    wrap.appendChild(body);
    return wrap;
  }

  function diseaseRows(diseases, kind) {
    return (diseases || []).map(function (disease) {
      return { _kind: kind, _id: disease.id, name: disease.name, mesh: disease.mesh };
    });
  }

  function reviewForm(detail, claim) {
    var form = document.createElement('div');
    form.setAttribute('class', 'ws-review');
    var statusLabel = document.createElement('label');
    statusLabel.setAttribute('for', 'ws-review-status');
    statusLabel.textContent = 'Status';
    var select = document.createElement('select');
    select.setAttribute('id', 'ws-review-status');
    select.setAttribute('class', 'ws-review-select');
    CLAIM_STATUSES.forEach(function (option) {
      var opt = document.createElement('option');
      opt.value = option;
      opt.textContent = option;
      select.appendChild(opt);
    });
    select.value = claim.status || 'pending';
    var notesLabel = document.createElement('label');
    notesLabel.setAttribute('for', 'ws-review-notes');
    notesLabel.textContent = 'Notes';
    var notes = document.createElement('textarea');
    notes.setAttribute('id', 'ws-review-notes');
    notes.setAttribute('class', 'ws-review-notes');
    notes.value = claim.notes || '';
    var save = document.createElement('button');
    save.setAttribute('type', 'button');
    save.setAttribute('class', 'ws-btn ws-btn-primary');
    save.textContent = 'Save';
    var saveStatus = document.createElement('p');
    saveStatus.setAttribute('class', 'ws-save-status');
    saveStatus.setAttribute('role', 'status');
    save.addEventListener('click', function () {
      save.disabled = true;
      saveStatus.setAttribute('class', 'ws-save-status');
      saveStatus.textContent = 'Saving…';
      fetch('/api/claims/' + claim.id + '/', {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-CSRFToken': csrfToken()
        },
        body: JSON.stringify({ status: select.value, notes: notes.value })
      })
        .then(function (response) {
          if (!response.ok) {
            throw new Error('Save failed: ' + response.status);
          }
          return response.json();
        })
        .then(function () {
          saveStatus.textContent = 'Saved.';
          save.disabled = false;
          loadList({ keepSelection: true });
          fetch('/api/claims/' + claim.id + '/', { headers: { Accept: 'application/json' } })
            .then(function (response) {
              if (!response.ok) {
                throw new Error('Reload failed');
              }
              return response.json();
            })
            .then(function (data) {
              if (state.selected && state.selected.tab === 'claims' && state.selected.id === claim.id) {
                state.detail = { tab: 'claims', id: claim.id, data: data };
                renderDetail('claims', data);
                var refreshed = document.querySelector('#ws-detail .ws-save-status');
                if (refreshed) {
                  refreshed.textContent = 'Saved.';
                }
              }
            })
            .catch(function () {
              saveStatus.setAttribute('class', 'ws-save-status is-error');
              saveStatus.textContent = 'Saved, but the detail could not be refreshed.';
            });
        })
        .catch(function (err) {
          save.disabled = false;
          saveStatus.setAttribute('class', 'ws-save-status is-error');
          saveStatus.textContent = err && err.message === 'Save failed: 403'
            ? 'Save rejected: missing or invalid CSRF token.'
            : 'Save failed. Your edits are preserved above.';
        });
    });
    form.appendChild(statusLabel);
    form.appendChild(select);
    form.appendChild(notesLabel);
    form.appendChild(notes);
    form.appendChild(save);
    form.appendChild(saveStatus);
    return form;
  }

  function renderClaimDetail(data) {
    clear(els.detail);
    var cols = document.createElement('div');
    cols.setAttribute('class', 'ws-cols');
    var left = document.createElement('div');
    left.setAttribute('class', 'ws-col-left');
    var right = document.createElement('div');
    right.setAttribute('class', 'ws-col-right');

    left.appendChild(make('h2', null, 'Claim ' + String(data.id)));
    left.appendChild(fieldList([
      ['ID', data.id, 'mono'],
      ['Type', data.claim_type],
      ['Section', data.section],
      ['Evidence', data.evidence],
      ['Status', data.status, 'badge'],
      ['Notes', data.notes],
      ['Trial', data.trial ? fkLink('trials', data.trial) : null],
      ['Publication', data.publication ? fkLink('publications', data.publication) : null],
      ['Chunk', data.chunk ? fkLink('chunks', data.chunk) : null],
      ['Created', data.created, 'mono'],
      ['Modified', data.modified, 'mono']
    ]));
    left.appendChild(judgementBox(data.judgements));
    left.appendChild(reviewForm(state.detail, data));

    right.appendChild(sectionHeading('Source'));
    right.appendChild(sourceBlock(data.section_text));
    right.appendChild(sectionHeading('Diseases'));
    right.appendChild(relatedTable(
      [{ key: 'name', label: 'Name' }, { key: 'mesh', label: 'MeSH', mono: true }],
      diseaseRows(data.diseases, 'diseases'),
      'No linked diseases.'
    ));
    right.appendChild(sectionHeading('Interventions'));
    right.appendChild(relatedTable(
      [{ key: 'name', label: 'Name' }, { key: 'mesh', label: 'MeSH', mono: true }],
      diseaseRows(data.interventions, 'interventions'),
      'No linked interventions.'
    ));
    right.appendChild(sectionHeading('Named entities'));
    right.appendChild(relatedTable(
      [
        { key: 'text', label: 'Text' },
        { key: 'label', label: 'Label' },
        { key: 'score', label: 'Score', numeric: true },
        { key: 'section', label: 'Section' }
      ],
      (data.ners || []).map(function (ner) {
        return { _kind: 'ners', _id: ner.id, text: ner.text, label: (ner.label || []).join(', '), score: ner.score, section: ner.section };
      }),
      'No named entities.'
    ));

    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
  }

  function renderDiseaseDetail(kind, data) {
    clear(els.detail);
    var cols = document.createElement('div');
    cols.setAttribute('class', 'ws-cols');
    var left = document.createElement('div');
    left.setAttribute('class', 'ws-col-left');
    var right = document.createElement('div');
    right.setAttribute('class', 'ws-col-right');
    left.appendChild(make('h2', null, kindLabel(kind) + ' ' + String(data.id)));
    left.appendChild(fieldList([
      ['ID', data.id, 'mono'],
      ['Name', data.name],
      ['MeSH', data.mesh, 'mono'],
      ['Created', data.created, 'mono'],
      ['Modified', data.modified, 'mono']
    ]));
    pagedRelatedTable(right, 'Claims', '/api/claims/?' + (kind === 'diseases' ? 'disease=' : 'intervention=') + data.id, 'No linked claims.');
    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
  }

  function renderTrialDetail(data) {
    clear(els.detail);
    var cols = document.createElement('div');
    cols.setAttribute('class', 'ws-cols');
    var left = document.createElement('div');
    left.setAttribute('class', 'ws-col-left');
    var right = document.createElement('div');
    right.setAttribute('class', 'ws-col-right');
    left.appendChild(make('h2', null, 'Trial ' + String(data.nct_id || data.id)));
    left.appendChild(fieldList([
      ['ID', data.id, 'mono'],
      ['NCT ID', data.nct_id, 'mono'],
      ['Title', data.title],
      ['Official title', data.official_title],
      ['Acronym', data.acronym],
      ['Status', data.status],
      ['Phase', data.phase],
      ['Study type', data.study_type],
      ['Lead sponsor', data.lead_sponsor],
      ['Start date', data.start_date, 'mono'],
      ['Has results', data.has_results],
      ['Created', data.created, 'mono'],
      ['Modified', data.modified, 'mono']
    ]));
    pagedRelatedTable(right, 'Claims', '/api/claims/?trial=' + data.id, 'No linked claims.');
    right.appendChild(sectionHeading('Publications'));
    right.appendChild(relatedTable(
      [
        { key: 'pmid', label: 'PMID', mono: true },
        { key: 'title', label: 'Title', excerpt: true },
        { key: 'journal', label: 'Journal' },
        { key: 'year', label: 'Year', numeric: true },
        { key: 'relation', label: 'Relation' }
      ],
      (data.linked_publications || []).map(function (pub) {
        return { _kind: 'publications', _id: pub.id, pmid: pub.pmid, title: pub.title, journal: pub.journal, year: pub.year, relation: pub.relation };
      }),
      'No linked publications.'
    ));
    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
  }

  function renderPublicationDetail(data) {
    clear(els.detail);
    var cols = document.createElement('div');
    cols.setAttribute('class', 'ws-cols');
    var left = document.createElement('div');
    left.setAttribute('class', 'ws-col-left');
    var right = document.createElement('div');
    right.setAttribute('class', 'ws-col-right');
    left.appendChild(make('h2', null, 'Publication ' + String(data.pmid || data.id)));
    left.appendChild(fieldList([
      ['ID', data.id, 'mono'],
      ['PMID', data.pmid, 'mono'],
      ['Title', data.title],
      ['Journal', data.journal],
      ['Year', data.year],
      ['Publication date', data.pub_date, 'mono'],
      ['DOI', data.doi, 'mono'],
      ['First author', data.first_author],
      ['Created', data.created, 'mono'],
      ['Modified', data.modified, 'mono']
    ]));
    pagedRelatedTable(right, 'Claims', '/api/claims/?publication=' + data.id, 'No linked claims.');
    right.appendChild(sectionHeading('Trials'));
    right.appendChild(relatedTable(
      [
        { key: 'nct_id', label: 'NCT ID', mono: true },
        { key: 'title', label: 'Title', excerpt: true },
        { key: 'status', label: 'Status' },
        { key: 'phase', label: 'Phase' },
        { key: 'relation', label: 'Relation' }
      ],
      (data.linked_trials || []).map(function (trial) {
        return { _kind: 'trials', _id: trial.id, nct_id: trial.nct_id, title: trial.title, status: trial.status, phase: trial.phase, relation: trial.relation };
      }),
      'No linked trials.'
    ));
    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
  }

  function renderDetail(tab, data) {
    if (tab === 'claims') {
      renderClaimDetail(data);
    } else if (tab === 'diseases' || tab === 'interventions') {
      renderDiseaseDetail(tab, data);
    } else if (tab === 'trials') {
      renderTrialDetail(data);
    } else if (tab === 'publications') {
      renderPublicationDetail(data);
    }
  }

  /* ---------- Shared detail modal ---------- */

  function showModalMode(mode) {
    els.modalBody.hidden = mode !== 'record';
    els.operation.hidden = mode !== 'operation';
    if (!els.modal.open) {
      els.modal.showModal();
    }
  }

  function operationRow(level, message, recordId, timestamp) {
    var row = make('div', 'ws-log-row');
    row.appendChild(make('time', 'mono', timestamp || new Date().toISOString()));
    var tag = String(level).toUpperCase();
    row.appendChild(make('span', 'ws-log-level ' +
      (tag === 'WARNING' ? 'warning' : tag === 'ERROR' ? 'error' : 'info'), tag));
    var content = document.createElement('span');
    content.textContent = String(message);
    if (recordId !== null && recordId !== undefined) {
      content.appendChild(document.createTextNode(' '));
      content.appendChild(openButton('Open ' + String(operation.currentId), operation.kind, recordId));
    }
    row.appendChild(content);
    els.operation.appendChild(row);
  }

  function setImportDisabled(disabled) {
    [els.importTrials, els.importPublications].forEach(function (form) {
      form.querySelectorAll('textarea, input, button').forEach(function (control) {
        control.disabled = disabled;
      });
    });
  }

  function parseImportIds(value, kind) {
    var raw = value.split(',').map(function (id) { return id.trim(); });
    if (!value.trim() || raw.some(function (id) { return !id; })) {
      throw new Error('Enter comma-separated IDs without empty entries.');
    }
    var ids = [];
    raw.forEach(function (entry) {
      var id = kind === 'trials' ? entry.toUpperCase() : entry;
      if (!(kind === 'trials' ? /^NCT[0-9]{8}$/.test(id) : /^[0-9]{1,64}$/.test(id))) {
        throw new Error('Enter valid ' + (kind === 'trials' ? 'NCT IDs' : 'PMIDs') + ' only.');
      }
      if (ids.indexOf(id) === -1) {
        ids.push(id);
      }
    });
    if (ids.length > 10) {
      throw new Error('Load at most 10 distinct IDs at a time.');
    }
    return ids;
  }

  async function submitImport(kind, form, event) {
    event.preventDefault();
    if (operation && operation.running) {
      return;
    }
    var field = form.querySelector('input[type="text"]');
    var error = form.querySelector('.ws-import-error');
    var ids;
    try {
      ids = parseImportIds(field.value, kind);
    } catch (validationError) {
      error.textContent = validationError.message;
      field.focus();
      return;
    }
    error.textContent = '';
    operation = { kind: kind, running: true, currentId: null };
    setImportDisabled(true);
    els.viewProgress.hidden = false;
    els.viewProgress.textContent = 'View progress';
    modalOpener = document.activeElement;
    els.modalTitle.textContent = 'Load ' + kind;
    clear(els.operation);
    var summary = make('p', 'ws-operation-summary', 'Starting');
    summary.setAttribute('role', 'status');
    els.operation.appendChild(summary);
    els.operation.appendChild(make('p', 'ws-operation-ids', 'IDs: ' + ids.join(', ')));
    operationRow('INFO', 'Starting ' + ids.length + ' import(s).');
    showModalMode('operation');

    var failed = [];
    var succeeded = 0;
    var partial = 0;
    for (var i = 0; i < ids.length; i += 1) {
      var id = ids[i];
      operation.currentId = id;
      summary.textContent = 'Loading ' + (i + 1) + ' of ' + ids.length + ': ' + id;
      operationRow('INFO', 'Loading ' + id + '…');
      try {
        var payload = kind === 'trials'
          ? { nct_id: id, load_related_publications: els.relatedPublications.checked }
          : { pmid: id };
        var response = await fetch('/api/import/' + kind + '/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json',
            'X-CSRFToken': csrfToken() },
          body: JSON.stringify(payload)
        });
        var data = await response.json();
        (Array.isArray(data.logs) ? data.logs : []).forEach(function (entry) {
          if (entry) {
            operationRow(entry.level || 'INFO', entry.message || '', null, entry.time);
          }
        });
        if (response.ok && data.status === 'ok') {
          succeeded += 1;
          operationRow('INFO', 'Saved ' + id + (data.related_publications === null ||
            data.related_publications === undefined ? '' :
            ' (' + data.related_publications + ' related publications).'), data.record_id);
        } else if (data.status === 'partial' && data.record_id !== undefined) {
          partial += 1;
          failed.push(id);
          operationRow('WARNING', 'Saved ' + id + ', but related publications could not be loaded. Retry this ID.',
            data.record_id);
        } else {
          failed.push(id);
          operationRow('ERROR', 'Could not load ' + id + '. Retry this ID.');
        }
      } catch (networkError) {
        failed.push(id);
        operationRow('ERROR', 'No response for ' + id + '. Retry this ID; the server may still be working.');
      }
    }
    summary.textContent = (failed.length ? (succeeded || partial ? 'Partial' : 'Failed') : 'Completed') +
      ': ' + succeeded + ' succeeded, ' + partial + ' partial, ' + (failed.length - partial) +
      ' failed of ' + ids.length + '.';
    operationRow('INFO', summary.textContent);
    field.value = failed.join(', ');
    operation.running = false;
    setImportDisabled(false);
    els.viewProgress.textContent = 'View results';
    if (state.tab === kind) {
      loadList({ keepSelection: true });
    }
  }

  function modalMessage(message) {
    clear(els.modalBody);
    els.modalBody.appendChild(make('p', 'ws-prompt', message));
  }

  function renderModalRecord(kind, data) {
    clear(els.modalBody);
    var dl = document.createElement('dl');
    dl.setAttribute('class', 'ws-fields');
    Object.keys(data).forEach(function (key) {
      if (key === 'raw' || key === 'meta' || key === 'raw_json') {
        return;
      }
      var value = data[key];
      if (value !== null && typeof value === 'object') {
        return;
      }
      var dt = document.createElement('dt');
      dt.textContent = key;
      var dd = document.createElement('dd');
      if (FK_KINDS[key] && (typeof value === 'number' || (typeof value === 'string' && /^[0-9]+$/.test(value)))) {
        dd.appendChild(openButton(kindLabel(FK_KINDS[key]) + ' ' + String(value), FK_KINDS[key], Number(value)));
      } else if (key === 'status' && (kind === 'claims')) {
        dd.appendChild(badgeCell(value === null || value === undefined ? '—' : value));
      } else {
        dd.textContent = value === null || value === undefined || value === '' ? '—' : String(value);
      }
      dl.appendChild(dt);
      dl.appendChild(dd);
    });
    els.modalBody.appendChild(dl);
    // Nested foreign records become link buttons; other objects become JSON.
    Object.keys(data).forEach(function (key) {
      var value = data[key];
      if (value === null || typeof value !== 'object') {
        return;
      }
      if (Array.isArray(value) && value.length && typeof value[0] === 'object' && value[0] !== null && value[0].id !== undefined) {
        var heading = make('h3', null, key);
        els.modalBody.appendChild(heading);
        value.forEach(function (entry) {
          var target = null;
          if (key === 'diseases') {
            target = 'diseases';
          } else if (key === 'interventions') {
            target = 'interventions';
          } else if (key === 'ners') {
            target = 'ners';
          } else if (key === 'judgements') {
            target = 'judgements';
          } else if (key === 'linked_publications') {
            target = 'publications';
          } else if (key === 'linked_trials') {
            target = 'trials';
          }
          var row = document.createElement('p');
          row.setAttribute('class', 'ws-log-row');
          var level = make('span', 'ws-log-level info', key);
          row.appendChild(level);
          var cell = document.createElement('span');
          if (target) {
            cell.appendChild(openButton(entryLabel(entry), target, entry.id));
          } else {
            cell.textContent = entryLabel(entry);
          }
          row.appendChild(cell);
          els.modalBody.appendChild(row);
        });
        return;
      }
      var details = document.createElement('details');
      var summary = document.createElement('summary');
      summary.textContent = key;
      details.appendChild(summary);
      var pre = document.createElement('pre');
      pre.setAttribute('class', 'ws-json');
      pre.textContent = JSON.stringify(value, null, 2);
      details.appendChild(pre);
      els.modalBody.appendChild(details);
    });
  }

  function entryLabel(entry) {
    var label = entry.nct_id || entry.pmid || entry.name || entry.title || entry.method || entry.text;
    return kindLabelGuess(entry) + ' ' + String(entry.id) + (label ? ' — ' + String(label).slice(0, 80) : '');
  }

  function kindLabelGuess(entry) {
    if (entry.nct_id) {
      return 'Trial';
    }
    if (entry.pmid) {
      return 'Publication';
    }
    if (entry.method && entry.score !== undefined && entry.claim === undefined) {
      return 'Judgement';
    }
    return 'Record';
  }

  function openRecord(kind, id) {
    var url = recordUrl(kind, id);
    if (!url) {
      return;
    }
    modalOpener = document.activeElement;
    clear(els.modalTitle);
    els.modalTitle.textContent = kindLabel(kind) + ' ' + String(id);
    modalMessage('Loading…');
    showModalMode('record');
    fetch(url, { headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (response.status === 404) {
          throw new Error('not found');
        }
        if (!response.ok) {
          throw new Error('failed');
        }
        return response.json();
      })
      .then(function (data) {
        renderModalRecord(kind, data);
      })
      .catch(function (err) {
        modalMessage(err && err.message === 'not found'
          ? 'Record not found.'
          : 'Could not load record. Check the connection and retry.');
      });
  }

  /* ---------- Shell wiring ---------- */

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
    els.operation = document.getElementById('ws-operation');
    els.importTrials = document.getElementById('ws-import-trials');
    els.importPublications = document.getElementById('ws-import-publications');
    els.relatedPublications = document.getElementById('ws-related-publications');
    els.viewProgress = document.getElementById('ws-view-progress');

    els.importTrials.addEventListener('submit', function (event) {
      submitImport('trials', els.importTrials, event);
    });
    els.importPublications.addEventListener('submit', function (event) {
      submitImport('publications', els.importPublications, event);
    });
    els.viewProgress.addEventListener('click', function () {
      modalOpener = document.activeElement;
      els.modalTitle.textContent = 'Load ' + operation.kind;
      showModalMode('operation');
    });

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
        state.detail = null;
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
    els.modal.addEventListener('close', function () {
      if (modalOpener && modalOpener.focus) {
        modalOpener.focus();
      }
      modalOpener = null;
    });

    renderImportForms();
    renderFilters();
    renderPrompt();
    loadList();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Exposed for the browser checks.
  window.workspace = {
    state: state,
    csrfToken: csrfToken,
    switchTab: switchTab,
    selectRow: selectRow,
    openRecord: openRecord
  };
})();
