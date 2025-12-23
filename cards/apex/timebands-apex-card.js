import { LitElement, html, css } from 'https://unpkg.com/lit-element@2.5.1/lit-element.js?module';

const DEFAULT_COLORS = {
  mattina: '#2e7d32',
  pomeriggio: '#ff8f00',
  sera: '#d84315',
  notte: '#1976d2',
};

class TimebandsApexCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _chart: { type: Object },
      _series: { type: Array },
      _labels: { type: Array },
      _colors: { type: Array },
    };
  }

  static getConfigElement() {
    return document.createElement('timebands-apex-card-editor');
  }

  static getStubConfig(hass, entities) {
    return {
      title: 'Consumo di ieri per fasce',
      bands: [
        { label: 'mattina', value_entity: 'sensor.tada_yesterday_mattina_value', percentage_entity: 'sensor.tada_yesterday_mattina_percentage' },
        { label: 'pomeriggio', value_entity: 'sensor.tada_yesterday_pomeriggio_value', percentage_entity: 'sensor.tada_yesterday_pomeriggio_percentage' },
        { label: 'sera', value_entity: 'sensor.tada_yesterday_sera_value', percentage_entity: 'sensor.tada_yesterday_sera_percentage' },
        { label: 'notte', value_entity: 'sensor.tada_yesterday_notte_value', percentage_entity: 'sensor.tada_yesterday_notte_percentage' },
      ],
      colors: {
        mattina: '#2e7d32',
        pomeriggio: '#ff8f00',
        sera: '#d84315',
        notte: '#1976d2',
      },
      size: 260,
      center_label: 'Totale',
      show_side_legend: true,
    };
  }

  setConfig(config) {
    if (!config || (!config.entity && !config.bands)) {
      throw new Error('Define either entity with timebands attribute or bands array.');
    }
    this.config = config;
  }

  connectedCallback() {
    super.connectedCallback();
    this._ensureApexLoaded();
  }

  _ensureApexLoaded() {
    if (window.ApexCharts) return;
    const existing = document.querySelector('script[data-apexcharts]');
    if (existing) return; // another card may be loading it
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/apexcharts';
    s.async = true;
    s.setAttribute('data-apexcharts', 'true');
    document.head.appendChild(s);
  }

  _getRawDataFromAttribute() {
    if (!this.hass || !this.config || !this.config.entity) return [];
    const entity = this.hass.states[this.config.entity];
    if (!entity) return [];
    const candidates = ['timebands', 'timebands_data', 'timebandsJson', 'timebands_json'];
    let attr;
    for (const key of candidates) {
      if (entity.attributes && entity.attributes[key] !== undefined) {
        attr = entity.attributes[key];
        break;
      }
    }
    if (!attr) return [];
    if (attr && Array.isArray(attr)) return attr;
    if (attr && attr.data && Array.isArray(attr.data)) return attr.data;
    return [];
  }

  _getRawDataFromBands() {
    if (!this.hass || !this.config || !Array.isArray(this.config.bands)) return [];
    return this.config.bands.map(b => {
      const pctState = b.percentage_entity ? this.hass.states[b.percentage_entity] : null;
      const valState = b.value_entity ? this.hass.states[b.value_entity] : null;
      const pct = pctState && pctState.state !== undefined ? Number(pctState.state) : null;
      const val = valState && valState.state !== undefined ? Number(valState.state) : null;
      return { label: b.label || (pctState ? pctState.attributes.friendly_name : (valState ? valState.attributes.friendly_name : '')), percentage: pct, value: val };
    });
  }

  _normalizeData(raw) {
    const data = raw.map(d => ({
      label: d.label,
      value: typeof d.value === 'number' ? d.value : (d.value ? Number(d.value) : null),
      percentage: typeof d.percentage === 'number' ? d.percentage : (d.percentage ? Number(d.percentage) : null),
    }));

    const haveValues = data.every(d => typeof d.value === 'number');
    if (haveValues) {
      const total = data.reduce((s, d) => s + (d.value || 0), 0);
      if (total > 0) {
        return data.map(d => ({ label: d.label, value: d.value, percentage: ((d.value || 0) / total) * 100 }));
      }
    }
    // Fall back to provided percentages
    return data.map(d => ({ label: d.label, value: d.value, percentage: typeof d.percentage === 'number' ? d.percentage : 0 }));
  }

  _colorForLabel(label) {
    const map = this.config.colors || DEFAULT_COLORS;
    const key = (label || '').toLowerCase().trim();
    return map[key] || '#888';
  }

  _computeDisplayData() {
    const raw = this.config.bands ? this._getRawDataFromBands() : this._getRawDataFromAttribute();
    const normalized = this._normalizeData(raw);
    const labels = normalized.map(d => d.label || '');
    const series = normalized.map(d => Math.max(0, Math.min(100, Number(d.percentage || 0))));
    const colors = normalized.map(d => this._colorForLabel(d.label));
    const totalValue = normalized.reduce((s, d) => s + (typeof d.value === 'number' ? d.value : 0), 0);
    const sum = series.reduce((s, v) => s + (Number.isFinite(v) ? v : 0), 0);
    const hasNaN = series.some(v => Number.isNaN(v));
    if (!series.length || sum <= 0 || hasNaN) {
      return { labels: ['No data'], series: [1], colors: ['#888'], normalized: [], totalValue: 0 };
    }
    return { labels, series, colors, normalized, totalValue };
  }

  firstUpdated() {
    this._maybeInitChart();
  }

  updated(changed) {
    if (changed.has('hass') || changed.has('config')) {
      this._updateChart();
    }
  }

  _maybeInitChart() {
    if (!this.renderRoot) return;
    const el = this.renderRoot.querySelector('.apex-host');
    if (!el) return;
    if (this._chart) return;
    const doInit = () => {
      const { labels, series, colors, totalValue, normalized } = this._computeDisplayData();
      const values = (normalized || []).map(d => Number(d.value || 0));
      const size = this.config.size || 260;
      const options = {
        chart: {
          type: 'donut',
          animations: { enabled: false },
          toolbar: { show: false },
          events: {
            dataPointMouseEnter: (event, chartContext, config) => {
              this._hoverIndex = (config && typeof config.dataPointIndex === 'number') ? config.dataPointIndex : -1;
              this.requestUpdate();
            },
            dataPointMouseLeave: () => {
              this._hoverIndex = -1;
              this.requestUpdate();
            }
          }
        },
        labels,
        series,
        colors,
        stroke: { width: 0 },
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: function (val) { return Math.round(val) + '%'; },
          dropShadow: { enabled: false },
        },
        states: {
          hover: { filter: { type: 'none' } },
          active: { filter: { type: 'none' } }
        },
        tooltip: {
          enabled: false,
        },
        plotOptions: {
          pie: {
            startAngle: -90,
            endAngle: 90,
            expandOnClick: false,
            donut: {
              size: '65%',
              labels: { show: false }
            }
          }
        },
      };
      this._chart = new ApexCharts(el, options);
      this._chart.render();
    };
    if (window.ApexCharts) {
      doInit();
    } else {
      // retry once ApexCharts loads
      const int = setInterval(() => {
        if (window.ApexCharts) {
          clearInterval(int);
          doInit();
        }
      }, 150);
    }
  }

  _updateChart() {
    if (!this._chart) {
      this._maybeInitChart();
      return;
    }
    const { labels, series, colors } = this._computeDisplayData();
    // Update options and series
    this._chart.updateOptions({
      labels,
      colors,
      tooltip: { enabled: false },
    }, false, true);
    this._chart.updateSeries(series, true);
  }

  _formatValue(v) {
    if (v === undefined || v === null) return '-';
    return Number(v).toFixed(2);
  }

  render() {
    const { labels, normalized, colors, totalValue } = this._computeDisplayData();
    const values = (normalized || []).map(d => Number(d.value || 0));
    const size = this.config.size || 260;
    const showSideLegend = this.config.show_side_legend !== false;
    const hovered = typeof this._hoverIndex === 'number' && this._hoverIndex >= 0;
    const centerLabel = hovered && labels[this._hoverIndex] ? labels[this._hoverIndex] : (this.config.center_label || 'Totale');
    const centerValue = hovered && values[this._hoverIndex] !== undefined ? Number(values[this._hoverIndex]).toFixed(2) : Number(totalValue).toFixed(2);
    return html`
      <ha-card>
        <div class="card-header">
          <div class="title">${this.config.title || 'Consumo per fasce (Apex)'}</div>
        </div>
        <div class="chart-row">
          <div class="chart-wrap" style="width:${size}px; height:${Math.round(size * 0.6)}px;">
            <div class="apex-host" style="width:${size}px; height:${Math.round(size * 0.6)}px;"></div>
            <div class="center-overlay">
              <div class="co-label">${centerLabel}</div>
              <div class="co-value">${centerValue} kWh</div>
            </div>
          </div>
          ${showSideLegend ? html`
            <div class="legend">
              ${normalized.map((d, i) => html`
                <div class="legend-item">
                  <span class="swatch" style="background:${colors[i]}"></span>
                  <div class="legend-text">
                    <div class="label">${d.label}</div>
                    <div class="value">${this._formatValue(d.value)} kWh • ${Math.round(d.percentage || 0)}%</div>
                  </div>
                </div>
              `)}
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; }
      .card-header { padding: 12px 16px 0 16px; }
      .title { font-weight: 600; font-size: 1.05rem; }
      .chart-row { display: flex; align-items: center; padding: 8px 16px 16px 16px; gap: 16px; }
      .chart-wrap { position: relative; }
      .center-overlay { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); display: flex; flex-direction: column; align-items: center; pointer-events: none; text-align: center; }
      .co-label { font-size: 0.9rem; color: var(--secondary-text-color); text-transform: capitalize; }
      .co-value { font-weight: 700; font-size: 1rem; }
      .legend { flex: 1; display: flex; flex-direction: column; gap: 8px; }
      .legend-item { display:flex; align-items:center; }
      .swatch { width:14px; height:14px; border-radius:3px; margin-right:10px; flex:0 0 14px; }
      .legend-text { display:flex; justify-content:space-between; width:100%; }
      .label { font-weight:600; text-transform:capitalize; }
      .value { color: var(--secondary-text-color, #666); font-size:0.95rem; }
      @media (max-width:420px) {
        .chart-row { flex-direction: column; align-items: center; gap: 12px; }
      }
    `;
  }

  getCardSize() { return 3; }
}

customElements.define('timebands-apex-card', TimebandsApexCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'timebands-apex-card',
  name: 'Timebands Apex Card',
  description: 'Semi-donut (ApexCharts) of timebands from sensors or entity attribute',
  preview: true
});

// ---------- Visual Editor ----------
const fireEvent = (node, type, detail) => {
  const event = new CustomEvent(type, { detail, bubbles: true, composed: true });
  node.dispatchEvent(event);
};

class TimebandsApexCardEditor extends LitElement {
  static get properties() {
    return {
      hass: {},
      lovelace: {},
      _config: {},
      _useBands: { type: Boolean },
      _debounceTimer: {},
      _suppressEmit: { type: Boolean },
      _pendingEmit: { type: Boolean },
    };
  }

  setConfig(config) {
    this._config = { ...config };
    this._useBands = !!(config && config.bands);
  }

  get value() { return this._config; }

  _updateConfig(partial, immediate = false) {
    this._config = { ...this._config, ...partial };
    this.requestUpdate();
    this._scheduleEmitConfig(immediate);
  }

  _scheduleEmitConfig(immediate = false) {
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = undefined;
    }
    if (immediate) {
      if (this._suppressEmit) {
        this._pendingEmit = true;
        return;
      }
      fireEvent(this, 'config-changed', { config: this._config });
      return;
    }
    this._debounceTimer = setTimeout(() => {
      if (this._suppressEmit) {
        this._pendingEmit = true;
        return;
      }
      fireEvent(this, 'config-changed', { config: this._config });
    }, 600);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = undefined;
      fireEvent(this, 'config-changed', { config: this._config });
    }
  }

  // HA component handlers
  _onHaValueChanged(e, key) {
    const v = (e && e.detail && e.detail.value !== undefined) ? e.detail.value : (e && e.target ? e.target.value : undefined);
    this._updateConfig({ [key]: v });
  }

  _onHaNumberChanged(e, key) {
    const vRaw = (e && e.detail && e.detail.value !== undefined) ? e.detail.value : (e && e.target ? e.target.value : undefined);
    const v = Number(vRaw);
    if (!isNaN(v)) this._updateConfig({ [key]: v });
  }

  _onHaSwitchChanged(e, key) {
    const checked = e && e.target ? !!e.target.checked : false;
    this._updateConfig({ [key]: checked });
  }

  _toggleModeSelect(e) {
    const value = (e && e.detail && e.detail.value !== undefined) ? e.detail.value : (e && e.target ? e.target.value : undefined);
    const useBands = value === 'bands';
    this._useBands = useBands;
    const cfg = { ...this._config };
    if (useBands) {
      delete cfg.entity;
      cfg.bands = cfg.bands || [];
    } else {
      delete cfg.bands;
      cfg.entity = cfg.entity || '';
    }
    this._updateConfig(cfg, true);
  }

  _onHaColorChanged(e, key) {
    const val = (e && e.detail && e.detail.value !== undefined) ? e.detail.value : (e && e.target ? e.target.value : undefined);
    const colors = { ...(this._config.colors || {}) };
    colors[key] = val;
    this._updateConfig({ colors });
  }

  _onHaEntityChanged(val) {
    this._updateConfig({ entity: val }, false);
  }

  _addBand() {
    const bands = Array.isArray(this._config.bands) ? [...this._config.bands] : [];
    bands.push({ label: '', value_entity: '', percentage_entity: '' });
    this._updateConfig({ bands }, true);
  }

  _removeBand(idx) {
    const bands = [...(this._config.bands || [])];
    bands.splice(idx, 1);
    this._updateConfig({ bands }, true);
  }

  _editBand(idx, key, value, immediate = false) {
    const bands = [...(this._config.bands || [])];
    bands[idx] = { ...(bands[idx] || {}), [key]: value };
    this._updateConfig({ bands }, immediate);
  }

  _sensorEntities() {
    const states = (this.hass && this.hass.states) ? this.hass.states : {};
    const items = Object.keys(states)
      .filter(id => id.startsWith('sensor.'))
      .map(id => ({ id, name: (states[id] && states[id].attributes && states[id].attributes.friendly_name) ? states[id].attributes.friendly_name : id }));
    items.sort((a, b) => a.name.localeCompare(b.name));
    return items;
  }

  _renderEntityPicker(currentValue, onChange, includeDomains = ['sensor'], label = '') {
    const hasEntityPicker = typeof customElements !== 'undefined' && customElements.get && customElements.get('ha-entity-picker');
    if (hasEntityPicker) {
      return html`
        <ha-entity-picker
          .hass=${this.hass}
          .value=${currentValue || ''}
          .includeDomains=${includeDomains}
          label=${label}
          @focus=${() => { this._suppressEmit = true; }}
          @blur=${() => { this._suppressEmit = false; if (this._pendingEmit) { this._pendingEmit = false; fireEvent(this, 'config-changed', { config: this._config }); } }}
          @opened=${() => { this._suppressEmit = true; }}
          @closed=${() => { this._suppressEmit = false; if (this._pendingEmit) { this._pendingEmit = false; fireEvent(this, 'config-changed', { config: this._config }); } }}
          @value-changed=${(e) => { e.stopPropagation(); onChange(e.detail && e.detail.value); }}
          style="width:100%"
        ></ha-entity-picker>
      `;
    }
    const hasHaSelect = typeof customElements !== 'undefined' && customElements.get && customElements.get('ha-select');
    const sensors = this._sensorEntities();
    if (hasHaSelect) {
      return html`
        <ha-select label=${label} .value=${currentValue || ''}
          @focus=${() => { this._suppressEmit = true; }}
          @blur=${() => { this._suppressEmit = false; if (this._pendingEmit) { this._pendingEmit = false; fireEvent(this, 'config-changed', { config: this._config }); } }}
          @opened=${() => { this._suppressEmit = true; }}
          @closed=${() => { this._suppressEmit = false; if (this._pendingEmit) { this._pendingEmit = false; fireEvent(this, 'config-changed', { config: this._config }); } }}
          @value-changed=${(e) => { e.stopPropagation(); onChange(e.detail && e.detail.value); }} style="width:100%">
          ${sensors.map(s => html`<mwc-list-item value="${s.id}">${s.name}</mwc-list-item>`)}
        </ha-select>
      `;
    }
    return html`
      <select class="fallback-select" style="width:100%"
        @focus=${() => { this._suppressEmit = true; }}
        @blur=${() => { this._suppressEmit = false; if (this._pendingEmit) { this._pendingEmit = false; fireEvent(this, 'config-changed', { config: this._config }); } }}
        @change=${(e) => { e.stopPropagation(); onChange(e.target.value); }}>
        <option value="">${label || '(select entity)'}</option>
        ${sensors.map(s => html`<option value="${s.id}" ?selected=${currentValue === s.id}>${s.name}</option>`)}
      </select>
    `;
  }

  render() {
    const cfg = this._config || {};
    const colors = cfg.colors || {};
    return html`
      <div class="editor">
        <div class="row">
            <ha-textfield label="Title" .value=${cfg.title || ''} @value-changed=${e => { e.stopPropagation(); this._onHaValueChanged(e, 'title'); }} style="width:100%"></ha-textfield>
        </div>
        <div class="row">
            <ha-textfield label="Size" type="number" min="120" .value=${cfg.size || 260} @value-changed=${e => { e.stopPropagation(); this._onHaNumberChanged(e, 'size'); }} style="width:100%"></ha-textfield>
        </div>
        <div class="row">
          <ha-formfield label="Show side legend">
              <ha-switch .checked=${cfg.show_side_legend !== false} @change=${e => { e.stopPropagation(); this._onHaSwitchChanged(e, 'show_side_legend'); }}></ha-switch>
          </ha-formfield>
        </div>

        <div class="row">
          <ha-select label="Mode" .value=${this._useBands ? 'bands' : 'entity'} @selected=${e => { e.stopPropagation(); this._toggleModeSelect(e); }} @value-changed=${e => { e.stopPropagation(); this._toggleModeSelect(e); }} style="width:100%">
            <mwc-list-item value="bands">Bands (entities)</mwc-list-item>
            <mwc-list-item value="entity">Single entity (timebands attr)</mwc-list-item>
          </ha-select>
        </div>

        ${this._useBands ? html`
          <div class="section">
            <div class="section-title">Bands</div>
            ${(cfg.bands || []).map((b, i) => html`
              <div class="band-row">
                <ha-textfield class="label" label="Band label" .value=${b.label || ''} @value-changed=${e => { e.stopPropagation(); this._editBand(i, 'label', (e.detail && e.detail.value) || e.target.value); }} style="width:100%"></ha-textfield>
                ${this._renderEntityPicker(b.value_entity, (val) => this._editBand(i, 'value_entity', val, false), ['sensor'], 'Value entity')}
                ${this._renderEntityPicker(b.percentage_entity, (val) => this._editBand(i, 'percentage_entity', val, false), ['sensor'], 'Percentage entity (optional)')}
                <div class="band-actions">
                  <button class="danger" @click=${() => this._removeBand(i)}>Remove</button>
                </div>
              </div>
            `)}
            <button @click=${this._addBand}>Add band</button>
          </div>
        ` : html`
          <div class="section">
            <div class="section-title">Entity</div>
            ${this._renderEntityPicker(cfg.entity, (val) => this._onHaEntityChanged(val), ['sensor'], 'Entity with timebands attribute')}
          </div>
        `}

        <div class="section">
          <div class="section-title">Colors</div>
          <div class="row">
            <ha-textfield label="Mattina" .value=${colors.mattina || '#2e7d32'} @value-changed=${e => this._onHaColorChanged(e, 'mattina')} style="width:100%"></ha-textfield>
          </div>
          <div class="row">
            <ha-textfield label="Pomeriggio" .value=${colors.pomeriggio || '#ff8f00'} @value-changed=${e => this._onHaColorChanged(e, 'pomeriggio')} style="width:100%"></ha-textfield>
          </div>
          <div class="row">
            <ha-textfield label="Sera" .value=${colors.sera || '#d84315'} @value-changed=${e => this._onHaColorChanged(e, 'sera')} style="width:100%"></ha-textfield>
          </div>
          <div class="row">
            <ha-textfield label="Notte" .value=${colors.notte || '#1976d2'} @value-changed=${e => this._onHaColorChanged(e, 'notte')} style="width:100%"></ha-textfield>
          </div>
        </div>
      </div>
    `;
  }

  static get styles() {
    return css`
      .editor { display: flex; flex-direction: column; gap: 10px; padding: 6px 0; }
      .row { display: grid; grid-template-columns: 1fr; gap: 8px; align-items: center; }
      .section { border-top: 1px solid var(--divider-color, #ddd); padding-top: 10px; margin-top: 6px; display: flex; flex-direction: column; gap: 8px; }
      .section-title { font-weight: 600; color: var(--primary-text-color); }
      .band-row { display: flex; flex-direction: column; gap: 10px; padding: 10px; border: 1px solid var(--divider-color, #ddd); border-radius: 6px; background: var(--card-background-color); }
      .band-actions { display: flex; justify-content: flex-end; }
      ha-textfield, ha-select, ha-entity-picker { width: 100%; }
      .fallback-select { padding: 8px; border-radius: 6px; border: 1px solid var(--divider-color, #ddd); background: var(--card-background-color); color: var(--primary-text-color); }
      input[type="checkbox"] { width: auto; }
      button { padding: 6px 10px; border-radius: 4px; border: 1px solid var(--primary-color); background: var(--primary-color); color: var(--text-primary-color, #fff); cursor: pointer; }
      button.danger { border-color: #c62828; background: #c62828; }
    `;
  }
}

customElements.define('timebands-apex-card-editor', TimebandsApexCardEditor);
