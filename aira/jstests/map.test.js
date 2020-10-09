L = {  // eslint-disable-line
  KML: jest.fn(),
};

aira = {};
require('../static/js/aira');

describe('map', () => {
  const KMLReturnValue = { addTo: jest.fn() };

  beforeAll(() => {
    aira.map.layerSwitcher = { addOverlay: jest.fn() };
    L.KML.mockReturnValue(KMLReturnValue);
    aira.strings = { covered_area: 'Covered area' };
  });

  test('adds covered area to layerswitcher', () => {
    aira.map.addCoveredAreaLayer();
    expect(aira.map.layerSwitcher.addOverlay).toHaveBeenCalledWith(
      KMLReturnValue, 'Covered area',
    );
  });
});
