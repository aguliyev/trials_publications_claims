/* Review workspace: tabbed tables over the Phase 1 list/detail API. */
(function () {
  'use strict';

  var TABS = {
    'claim-groups': {
      label: 'ClaimGroups',
      endpoint: '/api/claim-groups/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'evidence_summary_excerpt', label: 'Evidence summary', sortable: true, sortKey: 'evidence_summary', excerpt: true },
        { key: 'max_judgement_score', label: 'Max judgement', sortable: true, numeric: true },
        { key: 'claims_count', label: 'Claims', sortable: true, numeric: true },
        { key: 'diseases_count', label: 'Diseases', sortable: true, numeric: true },
        { key: 'interventions_count', label: 'Interventions', sortable: true, numeric: true }
      ],
      filters: []
    },
    claims: {
      label: 'Claims',
      endpoint: '/api/claims/',
      columns: [
        { key: 'id', label: 'ID', sortable: true, numeric: true },
        { key: 'claim_type', label: 'Type', sortable: true },
        { key: 'evidence_excerpt', label: 'Evidence', sortable: true, sortKey: 'evidence', excerpt: true },
        { key: 'source_label', label: 'Source', sortable: true, sortKey: 'source_sort' },
        { key: 'section', label: 'Section', sortable: true },
        { key: 'status', label: 'Status', sortable: true, badge: true },
        { key: 'max_judgement_score', label: 'Judgement', sortable: true, numeric: true },
        { key: 'modified', label: 'Modified', sortable: true, mono: true, datetime: true }
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
        { key: 'claims_count', label: 'Claims', sortable: true, numeric: true },
        { key: 'modified', label: 'Modified', sortable: true, mono: true, datetime: true }
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
        { key: 'claims_count', label: 'Claims', sortable: true, numeric: true },
        { key: 'modified', label: 'Modified', sortable: true, mono: true, datetime: true }
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
        { key: 'claims_count', label: 'Claims', sortable: true, numeric: true },
        { key: 'publications_count', label: 'Publ (DB / refs)', sortable: true, numeric: true, publicationRatio: true },
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
        { key: 'claims_count', label: 'Claims', sortable: true, numeric: true },
        { key: 'journal', label: 'Journal', sortable: true },
        { key: 'year', label: 'Year', sortable: true, numeric: true },
        { key: 'pub_date', label: 'Date', sortable: true, mono: true }
      ],
      filters: [
        { name: 'year', label: 'Year', type: 'text' },
        { name: 'journal', label: 'Journal', type: 'text' },
        { name: 'trial', label: 'Trial ID', type: 'text' }
      ]
    },
    sources: {
      label: 'Sources',
      endpoint: '/api/sources/',
      columns: [
        { key: 'id', label: 'Source ID', sortable: true, mono: true },
        { key: 'title', label: 'Title', sortable: true, excerpt: true },
        { key: 'publication_count', label: 'Publications', sortable: true, numeric: true },
        { key: 'database_record_id', label: 'In DB', sortable: true, inDatabase: true }
      ],
      filters: []
    }
  };

  var MAIN_KINDS = {
    'claim-groups': '/api/claim-groups/',
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
    'claim-groups': 'ClaimGroup',
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
    claim_group: 'claim-groups',
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
    tab: 'claim-groups',
    search: '',
    filters: {},
    ordering: null,
    page: 1,
    selected: null,
    detail: null,
    controller: null,
    seq: 0,
    sourceKind: 'publications',
    sourceResults: []
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
    var col = currentConfig().columns.find(function (candidate) { return candidate.key === base; });
    var sortField = col && col.sortKey || base;
    var tie = field.charAt(0) === '-' ? '-id' : 'id';
    if (base === 'id') {
      return field;
    }
    return (field.charAt(0) === '-' ? '-' : '') + sortField + ',' + tie;
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
    visibleColumns().forEach(function (col, index) {
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
          if (state.tab === 'sources') {
            renderHead();
            renderRows(state.sourceResults);
          } else {
            loadList();
          }
        });
        th.appendChild(btn);
      } else {
        th.textContent = col.label;
      }
      tr.appendChild(th);
    });
    els.thead.appendChild(tr);
  }

  function visibleColumns() {
    return currentConfig().columns.filter(function (col) {
      return state.tab !== 'sources' || state.sourceKind === 'trials' || col.key !== 'publication_count';
    });
  }

  function cellValue(row, col) {
    if (col.publicationRatio) {
      return row.publications_count + ' / ' + row.references_count;
    }
    var value = row[col.key];
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    if (value === null || value === undefined || value === '') {
      return null;
    }
    return value;
  }

  function formatDateTime(value) {
    if (value === null || value === undefined || value === '') {
      return value;
    }
    var match = String(value).match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})/);
    return match ? match[1] + ' ' + match[2] : String(value);
  }

  function renderRows(results) {
    clear(els.tbody);
    var config = currentConfig();
    if (state.tab === 'sources' && state.ordering) {
      var descending = state.ordering.charAt(0) === '-';
      var key = descending ? state.ordering.slice(1) : state.ordering;
      results = results.slice().sort(function (a, b) {
        var left = key === 'database_record_id' ? Number(a[key] != null) : a[key];
        var right = key === 'database_record_id' ? Number(b[key] != null) : b[key];
        var order = typeof left === 'number' && typeof right === 'number'
          ? left - right
          : String(left == null ? '' : left).localeCompare(String(right == null ? '' : right), undefined, { numeric: true, sensitivity: 'base' });
        return descending ? -order : order;
      });
    }
    results.forEach(function (row) {
      var tr = document.createElement('tr');
      if (state.selected && state.selected.tab === state.tab && state.selected.id === row.id) {
        tr.setAttribute('class', 'is-selected');
      }
      tr.addEventListener('click', function () {
        selectRow(row.id);
      });
      visibleColumns().forEach(function (col, index) {
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
        if (col.datetime && value !== null) {
          value = formatDateTime(value);
        }
        if (col.inDatabase) {
          if (value !== null) {
            var icon = make('span', 'ws-db-icon', '✓');
            icon.setAttribute('role', 'img');
            icon.setAttribute('aria-label', 'Already in database');
            td.appendChild(icon);
          }
        } else if (col.badge && value !== null) {
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
    els.controls.classList.toggle('is-claims', state.tab === 'claims');
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

  function renderSourceControls() {
    els.sourceForm.hidden = state.tab !== 'sources';
    els.controls.hidden = state.tab === 'sources';
    els.prev.hidden = state.tab === 'sources';
    els.next.hidden = state.tab === 'sources';
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
    if (state.tab === 'sources') {
      var source = state.sourceResults.find(function (row) { return row.id === id; });
      renderRows(state.sourceResults);
      if (source) {
        var selection = state.selected;
        var kind = state.sourceKind;
        var left = renderSourceDetail(source);
        left.appendChild(make('p', 'ws-prompt', 'Loading source details…'));
        fetch('/api/sources/' + kind + '/' + encodeURIComponent(String(id)) + '/',
          { headers: { Accept: 'application/json' } })
          .then(function (response) {
            if (!response.ok) {
              throw new Error('Source detail request failed');
            }
            return response.json();
          })
          .then(function (data) {
            if (state.selected !== selection) {
              return;
            }
            var databaseStatus = left.parentNode.querySelector('.ws-db-status');
            if (databaseStatus.textContent === 'Checking database…') {
              databaseStatus.textContent = data.database_record_id
                ? 'Already in database (record #' + data.database_record_id + ').'
                : 'Not in database.';
            }
            clear(left);
            left.appendChild(make('h2', null, kind === 'trials' ? 'Clinical trial' : 'Publication'));
            var entries = [[kind === 'trials' ? 'NCT ID' : 'PMID', source.id, 'external', kind],
              ['Title', data.title || source.title]];
            var fields = kind === 'trials' ? [
              ['Official title', data.official_title], ['Status', data.status],
              ['Phase', data.phase], ['Study type', data.study_type],
              ['Lead sponsor', data.lead_sponsor], ['Enrollment', data.enrollment],
              ['Conditions', data.conditions],
              ['Interventions', (data.interventions_list || []).map(function (item) { return item.name; })],
              ['Summary', data.summary], ['Detailed description', data.detailed_description],
              ['Eligibility criteria', data.eligibility_criteria]
            ] : [
              ['Journal', data.journal], ['Year', data.year], ['DOI', data.doi],
              ['First author', data.first_author], ['Authors', data.authors_str],
              ['Citation', data.citation], ['Abstract', data.abstract]
            ];
            left.appendChild(fieldList(entries.concat(fields.filter(function (entry) {
              return entry[1] !== null && entry[1] !== undefined && entry[1] !== '' &&
                (!Array.isArray(entry[1]) || entry[1].length > 0);
            }))));
            if (kind === 'trials') {
              var publications = data.publications || [];
              left.appendChild(sectionHeading('Publications (' + publications.length + ')'));
              if (!publications.length) {
                left.appendChild(emptyNote('No publications with a PMID listed.'));
              } else {
                var wrap = make('div', 'ws-table-wrap');
                var table = make('table', 'ws-table');
                var thead = document.createElement('thead');
                var head = document.createElement('tr');
                ['PMID', 'Citation', 'Type'].forEach(function (label) {
                  head.appendChild(make('th', null, label));
                });
                thead.appendChild(head);
                table.appendChild(thead);
                var tbody = document.createElement('tbody');
                publications.forEach(function (publication) {
                  var row = document.createElement('tr');
                  var pmid = document.createElement('td');
                  pmid.appendChild(externalRecordLink('publications', publication.pmid));
                  row.appendChild(pmid);
                  row.appendChild(make('td', null, publication.citation));
                  row.appendChild(make('td', null, publication.type));
                  tbody.appendChild(row);
                });
                table.appendChild(tbody);
                wrap.appendChild(table);
                left.appendChild(wrap);
              }
            }
          })
          .catch(function () {
            if (state.selected === selection) {
              var databaseStatus = left.parentNode.querySelector('.ws-db-status');
              if (databaseStatus.textContent === 'Checking database…') {
                databaseStatus.textContent = 'Database status unavailable.';
              }
              left.querySelector('.ws-prompt').textContent = 'Could not load details. Select the row again to retry.';
            }
          });
      }
      return;
    }
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
    if (state.controller) {
      state.controller.abort();
      state.controller = null;
    }
    state.seq += 1;
    renderSourceControls();
    renderFilters();
    renderPrompt();
    if (tab === 'sources') {
      renderHead();
      renderTabs();
      renderRows(state.sourceResults);
      setCount(state.sourceResults.length ? 1 : 0, state.sourceResults.length, state.sourceResults.length);
      setStatus(state.sourceResults.length ? '' : 'Search PubMed or ClinicalTrials.gov to find sources.', false);
    } else {
      loadList();
    }
  }

  function searchSources(event) {
    event.preventDefault();
    var query = els.sourceForm.elements.query.value.trim();
    if (!query) {
      setStatus('Enter a keyword.', true);
      return;
    }
    state.sourceKind = els.sourceForm.elements.kind.value;
    state.sourceResults = [];
    state.ordering = null;
    state.selected = null;
    renderPrompt();
    renderHead();
    renderRows([]);
    setCount(0, 0, 0);
    if (state.controller) {
      state.controller.abort();
    }
    var controller = new AbortController();
    state.controller = controller;
    var seq = ++state.seq;
    setStatus('Searching…', false);
    var params = new URLSearchParams({ kind: state.sourceKind, query: query });
    fetch('/api/sources/?' + params.toString(), { signal: controller.signal, headers: { Accept: 'application/json' } })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('Search failed');
        }
        return response.json();
      })
      .then(function (data) {
        if (seq !== state.seq || state.tab !== 'sources') {
          return;
        }
        state.sourceResults = data.results || [];
        renderRows(state.sourceResults);
        setCount(state.sourceResults.length ? 1 : 0, state.sourceResults.length, state.sourceResults.length);
        setStatus(state.sourceResults.length ? '' : 'No sources found.', false);
      })
      .catch(function (err) {
        if (err.name !== 'AbortError' && seq === state.seq && state.tab === 'sources') {
          setStatus('Could not search sources. Retry your search.', true);
        }
      });
  }

  /* ---------- Lower details ---------- */

  function externalRecordLink(kind, id) {
    var link = document.createElement('a');
    var base = kind === 'trials' ? 'https://clinicaltrials.gov/study/' : 'https://pubmed.ncbi.nlm.nih.gov/';
    link.href = base + encodeURIComponent(String(id)) + (kind === 'publications' ? '/' : '');
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = String(id);
    return link;
  }

  function renderSourceDetail(source) {
    clear(els.detail);
    var cols = make('div', 'ws-cols');
    var left = make('div', 'ws-col-left');
    var right = make('div', 'ws-col-right');
    var kind = state.sourceKind;
    left.appendChild(make('h2', null, kind === 'trials' ? 'Clinical trial' : 'Publication'));
    left.appendChild(fieldList([
      [kind === 'trials' ? 'NCT ID' : 'PMID', source.id, 'external', kind],
      ['Title', source.title]
    ]));
    var databaseStatus = make('p', 'ws-db-status', 'Checking database…');
    databaseStatus.setAttribute('role', 'status');
    right.appendChild(databaseStatus);
    right.appendChild(sectionHeading('Fetch into database'));
    var checkbox;
    if (kind === 'trials') {
      var label = make('label', 'ws-import-check');
      checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      label.appendChild(checkbox);
      label.appendChild(document.createTextNode(' Fetch with publications'));
      right.appendChild(label);
    }
    var button = make('button', 'ws-btn ws-btn-primary ws-source-fetch', 'Fetch ' + (kind === 'trials' ? 'trial' : 'publication'));
    button.type = 'button';
    var feedback = make('p', 'ws-save-status');
    feedback.setAttribute('role', 'status');
    button.addEventListener('click', function () {
      submitSourceImport(kind, source.id, checkbox && checkbox.checked, button, feedback, databaseStatus);
    });
    right.appendChild(button);
    right.appendChild(feedback);
    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
    return left;
  }

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
      } else if (entry[2] === 'external' && value) {
        dd.appendChild(externalRecordLink(entry[3], value));
        dd.setAttribute('class', 'mono');
      } else if (entry[2] === 'badge' && value !== null && value !== '') {
        dd.appendChild(badgeCell(value));
      } else if (value !== null && typeof value === 'object') {
        if (!Object.keys(value).length) {
          dd.textContent = '—';
        } else if (Array.isArray(value) && value.every(function (item) { return typeof item === 'string'; })) {
          dd.textContent = value.join(', ');
        } else {
          dd.appendChild(make('pre', 'ws-json', JSON.stringify(value, null, 2)));
        }
      } else if (value === null || value === undefined || value === '') {
        dd.textContent = '—';
      } else {
        dd.textContent = /^(created|modified)$/i.test(entry[0]) ? formatDateTime(value) : String(value);
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
          td.textContent = value === null || value === undefined || value === '' ? '—' :
            (col.datetime ? formatDateTime(value) : String(value));
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
      var meta = judgement.meta && typeof judgement.meta === 'object' ? judgement.meta : {};
      var line = judgement.method + (meta.model ? '/' + meta.model : '') + ' : ' +
        (meta.verdict ? meta.verdict + ' · ' : '') + String(judgement.score);
      item.textContent = line;
      if (Object.keys(meta).length && !meta.verdict && !meta.model) {
        var details = document.createElement('pre');
        details.setAttribute('class', 'ws-json mono');
        details.textContent = JSON.stringify(meta, null, 2);
        item.appendChild(details);
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

  function nerTable(ners) {
    return relatedTable(
      [
        { key: 'text', label: 'Text' },
        { key: 'label', label: 'Label' },
        { key: 'score', label: 'Score', numeric: true },
        { key: 'section', label: 'Section' }
      ],
      (ners || []).map(function (ner) {
        return { _kind: 'ners', _id: ner.id, text: ner.text, label: (ner.label || []).join(', '), score: ner.score, section: ner.section };
      }),
      'No named entities.'
    );
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

  function renderClaimGroupDetail(data) {
    clear(els.detail);
    var cols = make('div', 'ws-cols');
    var left = make('div', 'ws-col-left');
    var right = make('div', 'ws-col-right');
    left.appendChild(make('h2', null, 'ClaimGroup ' + String(data.id)));
    left.appendChild(fieldList([
      ['ID', data.id, 'mono'],
      ['Evidence summary', data.evidence_summary],
      ['Synced', data.synced],
      ['Created', data.created, 'mono'],
      ['Modified', data.modified, 'mono']
    ]));
    pagedRelatedTable(right, 'Claims', '/api/claims/?claim_group=' + data.id, 'No linked claims.');
    right.appendChild(sectionHeading('Trials'));
    right.appendChild(relatedTable(
      [{ key: 'nct_id', label: 'NCT ID', mono: true }, { key: 'title', label: 'Title', excerpt: true },
        { key: 'status', label: 'Status' }, { key: 'phase', label: 'Phase' }],
      (data.trials || []).map(function (trial) {
        return { _kind: 'trials', _id: trial.id, nct_id: trial.nct_id, title: trial.title,
          status: trial.status, phase: trial.phase };
      }), 'No trials linked through claims.'
    ));
    right.appendChild(sectionHeading('Publications'));
    right.appendChild(relatedTable(
      [{ key: 'pmid', label: 'PMID', mono: true }, { key: 'title', label: 'Title', excerpt: true },
        { key: 'journal', label: 'Journal' }, { key: 'year', label: 'Year', numeric: true }],
      (data.publications || []).map(function (publication) {
        return { _kind: 'publications', _id: publication.id, pmid: publication.pmid,
          title: publication.title, journal: publication.journal, year: publication.year };
      }), 'No publications linked through claims.'
    ));
    right.appendChild(sectionHeading('Diseases'));
    right.appendChild(relatedTable(
      [{ key: 'name', label: 'Name' }, { key: 'mesh', label: 'MeSH', mono: true }],
      diseaseRows(data.diseases, 'diseases'), 'No linked diseases.'
    ));
    right.appendChild(sectionHeading('Interventions'));
    right.appendChild(relatedTable(
      [{ key: 'name', label: 'Name' }, { key: 'mesh', label: 'MeSH', mono: true }],
      diseaseRows(data.interventions, 'interventions'), 'No linked interventions.'
    ));
    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
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
      ['ClaimGroup', data.claim_group ? fkLink('claim-groups', data.claim_group) : null],
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
    right.appendChild(nerTable(data.ners));

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
      ['NCT ID', data.nct_id, 'external', 'trials'],
      ['Title', data.title],
      ['Official title', data.official_title],
      ['Acronym', data.acronym],
      ['Organization', data.organization],
      ['Status', data.status],
      ['Phase', data.phase],
      ['Study type', data.study_type],
      ['Lead sponsor', data.lead_sponsor],
      ['Conditions', data.conditions],
      ['Interventions', data.interventions_list],
      ['Summary', data.summary],
      ['Detailed description', data.detailed_description],
      ['Enrollment', data.enrollment],
      ['Eligible sex', data.sex],
      ['Minimum age', data.minimum_age],
      ['Maximum age', data.maximum_age],
      ['Eligibility criteria', data.eligibility_criteria],
      ['Study design', data.design_info],
      ['Arms', data.arms],
      ['Outcomes', data.outcomes],
      ['Start date', data.start_date, 'mono'],
      ['Primary completion date', data.primary_completion_date, 'mono'],
      ['Completion date', data.completion_date, 'mono'],
      ['Last update', data.last_update_posted_date, 'mono'],
      ['Has results', data.has_results],
      ['Keywords', data.keywords],
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
    right.appendChild(sectionHeading('Named entities'));
    right.appendChild(nerTable(data.ners));
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
      ['PMID', data.pmid, 'external', 'publications'],
      ['Title', data.title],
      ['Abstract', data.abstract],
      ['Journal', data.journal],
      ['Year', data.year],
      ['Publication date', data.pub_date, 'mono'],
      ['Volume', data.volume],
      ['Issue', data.issue],
      ['Pages', data.pages],
      ['DOI', data.doi, 'mono'],
      ['PMC', data.pmc, 'mono'],
      ['First author', data.first_author],
      ['Authors', data.authors_str || data.authors],
      ['Citation', data.citation],
      ['Publication type', data.pubmed_type],
      ['Keywords', data.keywords],
      ['MeSH terms', data.mesh_terms],
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
    right.appendChild(sectionHeading('Named entities'));
    right.appendChild(nerTable(data.ners));
    cols.appendChild(left);
    cols.appendChild(right);
    els.detail.appendChild(cols);
  }

  function renderDetail(tab, data) {
    if (tab === 'claim-groups') {
      renderClaimGroupDetail(data);
    } else if (tab === 'claims') {
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

  async function submitSourceImport(kind, id, withPublications, button, feedback, databaseStatus) {
    if (operation && operation.running) {
      return;
    }
    operation = { kind: kind, running: true, currentId: id };
    button.disabled = true;
    feedback.textContent = 'Fetching ' + id + '…';
    els.viewProgress.hidden = false;
    els.viewProgress.textContent = 'View progress';
    els.modalTitle.textContent = 'Load ' + kind;
    clear(els.operation);
    var summary = make('p', 'ws-operation-summary', 'Loading ' + id + '…');
    summary.setAttribute('role', 'status');
    els.operation.appendChild(summary);
    try {
      var payload = kind === 'trials'
        ? { nct_id: id, load_related_publications: Boolean(withPublications) }
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
      if (data.record_id !== undefined && (data.status === 'ok' || data.status === 'partial') &&
          state.tab === 'sources' && state.sourceKind === kind) {
        var source = state.sourceResults.find(function (row) { return row.id === id; });
        if (source) {
          source.database_record_id = data.record_id;
          renderRows(state.sourceResults);
        }
      }
      if (response.ok && data.status === 'ok') {
        databaseStatus.textContent = 'Already in database (record #' + data.record_id + ').';
        feedback.textContent = 'Saved ' + id + ' to the database.' +
          (Array.isArray(data.related_publication_ids) ?
            ' Publication IDs: ' + (data.related_publication_ids.join(', ') || 'none') + '.' : '');
        operationRow('INFO', 'Saved ' + id + (data.related_publications == null ? '' :
          ' (' + data.related_publications + ' related publications).'), data.record_id);
      } else if (data.status === 'partial' && data.record_id !== undefined) {
        databaseStatus.textContent = 'Already in database (record #' + data.record_id + ').';
        feedback.textContent = 'Trial saved, but related publications could not be loaded. Retry to fetch them.';
        operationRow('WARNING', feedback.textContent, data.record_id);
      } else {
        feedback.textContent = 'Could not fetch ' + id + '. Retry this record.';
        operationRow('ERROR', feedback.textContent);
      }
    } catch (networkError) {
      feedback.textContent = 'No response for ' + id + '. Retry; the server may still be working.';
      operationRow('ERROR', feedback.textContent);
    }
    summary.textContent = feedback.textContent;
    operation.running = false;
    button.disabled = false;
    els.viewProgress.textContent = 'View results';
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
      dt.textContent = key === 'claim_group' ? 'ClaimGroup' : key;
      var dd = document.createElement('dd');
      if (FK_KINDS[key] && (typeof value === 'number' || (typeof value === 'string' && /^[0-9]+$/.test(value)))) {
        dd.appendChild(openButton(kindLabel(FK_KINDS[key]) + ' ' + String(value), FK_KINDS[key], Number(value)));
      } else if (value && ((kind === 'trials' && key === 'nct_id') || (kind === 'publications' && key === 'pmid'))) {
        dd.appendChild(externalRecordLink(kind, value));
      } else if (key === 'status' && (kind === 'claims')) {
        dd.appendChild(badgeCell(value === null || value === undefined ? '—' : value));
      } else {
        dd.textContent = value === null || value === undefined || value === '' ? '—' :
          (/^(created|modified)$/i.test(key) ? formatDateTime(value) : String(value));
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
      if (kind === 'claims' && key === 'judgements') {
        els.modalBody.appendChild(judgementBox(value));
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
    if (kind === 'claim-groups') {
      pagedRelatedTable(els.modalBody, 'Claims', '/api/claims/?claim_group=' + data.id, 'No linked claims.');
    }
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
    els.controls = document.querySelector('.ws-controls');
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
    els.sourceForm = document.getElementById('ws-source-search');
    els.viewProgress = document.getElementById('ws-view-progress');

    els.sourceForm.addEventListener('submit', searchSources);
    els.sourceForm.addEventListener('change', function (event) {
      if (event.target.name === 'kind') {
        state.sourceKind = event.target.value;
        state.sourceResults = [];
        state.selected = null;
        if (state.controller) {
          state.controller.abort();
        }
        state.seq += 1;
        renderRows([]);
        renderPrompt();
        setCount(0, 0, 0);
        setStatus('Search ' + (state.sourceKind === 'trials' ? 'ClinicalTrials.gov' : 'PubMed') + ' to find sources.', false);
      }
    });
    els.viewProgress.addEventListener('click', function () {
      modalOpener = document.activeElement;
      els.modalTitle.textContent = 'Load ' + operation.kind;
      showModalMode('operation');
    });

    var debounce = null;
    els.tabs.addEventListener('click', function (event) {
      var btn = event.target.closest('[data-tab]');
      if (btn) {
        window.clearTimeout(debounce);
        switchTab(btn.getAttribute('data-tab'));
      }
    });

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

    renderSourceControls();
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
