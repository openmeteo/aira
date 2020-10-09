moment = require('moment'); // eslint-disable-line
L = {  // eslint-disable-line
  tileLayer: {
    wms: jest.fn(),
  },
};

aira = {};
require('../static/js/aira');

describe('meteoMapPanel.updateMeteoLayer', () => {
  const tileLayerWmsReturnValue = { addTo: jest.fn() };
  aira.map.layerSwitcher = { addOverlay: jest.fn() };
  L.tileLayer.wms.mockReturnValue(tileLayerWmsReturnValue);
  aira.map.leafletMap = { removeLayer: jest.fn() };

  beforeEach(() => {
    document.body.innerHTML = `
      <a id='timestep-toggle' href='#' current-timestep='daily'>Switch to monthly</a>
      <form>
        <input id="date-input" value="2020-09-30">
        <select id='dailyMeteoVar'>
          <option value="Daily_rain_">Daily rainfall (mm/d)</option>
        </select>
      </form>
      <button id="previous-date">2020-01-13</button>
      <button id="current-date">2020-01-14</button>
      <button id="next-date">2020-01-15</button>
    `;
  });

  test('meteo raster is not hidden by background layer', () => {
    aira.meteoMapPanel.updateMeteoLayer();
    const layerOptions = L.tileLayer.wms.mock.calls[0][1];
    expect(layerOptions.zIndex).toBe(100);
  });

  test('updateMeteoLayer() adds meteo raster to layer switcher', () => {
    aira.meteoMapPanel.updateMeteoLayer();
    expect(aira.map.layerSwitcher.addOverlay).toHaveBeenCalled();

    /* The correct test would be the one below, but apparently jsdom does not
     * support HTMLSelectElement.options and/or HTMLSelectElement.selectedIndex,
     * which are how the main code determines the string to use when calling
     * addOverlay().
     */
    // expect(aira.map.layerSwitcher.addOverlay).toHaveBeenCalledWith(
    //  tileLayerWmsReturnValue, "Daily rainfall (mm/d)",
    // );
  });

  test('setMapDate changes activeDate as needed', () => {
    aira.meteoMapPanel.setMapDate('2020-10-02');
    expect(aira.meteoMapPanel.activeDate).toBe('2020-10-02');
  });
});
