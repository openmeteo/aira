moment = require('moment'); // eslint-disable-line
ApexCharts = jest.fn();  // eslint-disable-line
ApexCharts.mockReturnValue({
  render: jest.fn(),
  updateSeries: jest.fn(),
  updateOptions: jest.fn(),
});

aira = {};
require('../static/js/aira');

const savedDateNow = Date.now.bind(global.Date);
const getDate = (year, month, day) => new Date(year, month - 1, day);
const mockCurrentDate = (year, month, day) => {
  const mockDateNow = jest.fn(() => getDate(year, month, day).valueOf());
  global.Date.now = mockDateNow;
};
const unmockCurrentDate = () => {
  global.Date.Now = savedDateNow;
};

describe('initializeChart', () => {
  beforeAll(() => {
    document.body.innerHTML = `
      <div id="kc-chart"></div>
      <input id="id_custom_planting_date" value="15/03">
      <input id="id_custom_kc_initial" value="0.5">
      <input id="id_custom_kc_offseason" value="0.4">
      <textarea id="id_kc_stages">20,0.5\n10,0.6</textarea>
    `;
    mockCurrentDate(2018, 5, 5);
    aira.kcCharter.initializeChart();
  });

  afterAll(() => {
    unmockCurrentDate();
  });

  test('creates chart', () => {
    expect(ApexCharts).toHaveBeenCalled();
  });

  test('renders chart', () => {
    expect(aira.kcCharter.chart.render).toHaveBeenCalledWith();
  });
});

describe('updateChart', () => {
  beforeAll(() => {
    document.body.innerHTML = `
      <input id="id_custom_planting_date" value="15/03">
      <input id="id_custom_kc_initial" value="0.5">
      <input id="id_custom_kc_offseason" value="0.4">
      <textarea id="id_kc_stages">20,0.5\n10,0.52</textarea>
    `;
    mockCurrentDate(2018, 5, 5);
    aira.kcCharter.initialize();
  });

  test('calls updateSeries', () => {
    expect(aira.kcCharter.chart.updateSeries).toHaveBeenCalled();
  });

  test('calls updateOptions', () => {
    expect(aira.kcCharter.chart.updateOptions).toHaveBeenCalled();
  });

  test('sets min yaxis to 0.1', () => {
    expect(aira.kcCharter.chart.updateOptions.mock.calls[0][0].yaxis.min).toBe(0.1);
  });

  test('sets max yaxis to 0.6', () => {
    expect(aira.kcCharter.chart.updateOptions.mock.calls[0][0].yaxis.max).toBe(0.6);
  });

  test('sets tickAmount to 5', () => {
    expect(aira.kcCharter.chart.updateOptions.mock.calls[0][0].yaxis.tickAmount).toBe(5);
  });
});

describe('getChartSeries', () => {
  beforeAll(() => {
    document.body.innerHTML = `
      <input id="id_custom_planting_date" value="15/03">
      <input id="id_custom_kc_initial" value="0.5">
      <input id="id_custom_kc_offseason" value="0.4">
      <textarea id="id_kc_stages">20,0.5\n10,0.6</textarea>
    `;
    mockCurrentDate(2018, 5, 5);
  });

  afterAll(() => {
    unmockCurrentDate();
  });

  test('creates series properly', () => {
    expect(aira.kcCharter.getChartSeries()).toEqual(
      [{
        name: 'Kc',
        data: [
          { x: getDate(2018, 3, 10), y: 0.4 },
          { x: getDate(2018, 3, 15), y: 0.4 },
          { x: new Date(2018, 3 - 1, 15, 0, 0, 1), y: 0.5 },
          { x: getDate(2018, 4, 4), y: 0.5 },
          { x: getDate(2018, 4, 14), y: 0.6 },
        ],
      }],
    );
  });
});

describe('getKcStagesFromText', () => {
  const expectedResult = [
    { ndays: 25, kcEnd: 0.7 },
    { ndays: 15, kcEnd: 0.3 },
    { ndays: 5, kcEnd: 0.25 },
  ];

  const check = (input) => {
    expect(aira.kcCharter.getKcStagesFromText(input)).toEqual(expectedResult);
  };

  test('reads tab-delimited text', () => {
    check('25\t0.7\n15\t0.3\n5\t0.25');
  });

  test('reads space-delimited text', () => {
    check('25 0.7\n15 0.3\n5 0.25');
  });

  test('reads comma-delimited text', () => {
    check('25,0.7\n15,0.3\n5,0.25');
  });

  test('ignores leading and trailing spaces', () => {
    check('  25 0.7  \n  15,0.3  \n  5\t0.25 ');
  });

  test('ignores trailing newline', () => {
    check('25 0.7\n15 0.3\n5 0.25\n');
  });

  test('throws error on empty', () => {
    expect(() => aira.kcCharter.getKcStagesFromText('')).toThrowError();
  });

  test('works with <br> instead of newlines', () => {
    check('25 0.7<br>15 0.3<br>5 0.25');
  });

  test('works when wrapped in a <p>', () => {
    check('<p>25 0.7<br>15 0.3<br>5 0.25</p>');
  });
});

describe('getPlantingDate', () => {
  afterEach(() => {
    unmockCurrentDate();
  });

  test('returns specified planting date', () => {
    document.body.innerHTML = '<input id="id_custom_planting_date" value="13/04">';
    mockCurrentDate(2018, 8, 29);
    expect(aira.kcCharter.getPlantingDate()).toEqual(getDate(2018, 4, 13));
  });

  test('returns default planting date', () => {
    document.body.innerHTML = '<input id="id_custom_planting_date" value="garbage">';
    mockCurrentDate(2018, 8, 29);
    expect(aira.kcCharter.getPlantingDate()).toEqual(getDate(2018, 3, 15));
  });
});

describe('getDateFromDayMonth', () => {
  const getResult = aira.kcCharter.getDateFromDayMonth.bind(aira.kcCharter);

  afterEach(() => {
    unmockCurrentDate();
  });

  test('nearest is in this year', () => {
    mockCurrentDate(2018, 8, 29);
    expect(getResult('28/2')).toEqual(getDate(2018, 2, 28));
  });

  test('nearest is in next year', () => {
    mockCurrentDate(2018, 8, 29);
    expect(getResult('15/2')).toEqual(getDate(2019, 2, 15));
  });

  test('nearest is in previous year', () => {
    mockCurrentDate(2018, 6, 17);
    expect(getResult('20/12')).toEqual(getDate(2017, 12, 20));
  });
});

describe('getParameterValue', () => {
  beforeAll(() => {
    document.body.innerHTML = `
      <input id="input-element-id" value="hello">
      <p>Default value: <span id="default-value-id">42</span></p>
    `;
  });

  test('gets input element if available', () => {
    expect(
      aira.kcCharter.getParameterValue('input-element-id', 'default-value-id', (x) => x),
    ).toBe('hello');
  });

  test('gets fallback element if available', () => {
    expect(
      aira.kcCharter.getParameterValue(
        'input-element-id', 'default-value-id', aira.kcCharter.strToNum,
      ),
    ).toBe(42);
  });
});

describe('strToNum', () => {
  test('reads number ok', () => {
    expect(aira.kcCharter.strToNum('15.2')).toBe(15.2);
  });

  test('trims spaces ok', () => {
    expect(aira.kcCharter.strToNum('  15.2\t\n')).toBe(15.2);
  });

  test('throws error on invalid input', () => {
    expect(() => aira.kcCharter.strToNum('a')).toThrowError();
  });

  test('throws error on empty', () => {
    expect(() => aira.kcCharter.strToNum('')).toThrowError();
  });
});
