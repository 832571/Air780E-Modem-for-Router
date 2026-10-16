import json,re,unittest
from pathlib import Path

class TranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page=(Path(__file__).resolve().parents[1]/'files/usr/lib/lua/luci/view/air780e/dashboard.htm').read_text()
        catalog=(Path(__file__).resolve().parents[1]/'files/www/luci-static/resources/air780e/translations.js').read_text()
        cls.catalog=json.loads(catalog.removeprefix('window.Air780ETranslations=').strip().removesuffix(';'))
    def test_all_static_labels_have_both_translations(self):
        for key in re.findall(r'data-i18n(?:-placeholder|-aria-label)?="([^"]+)"',self.page):
            with self.subTest(key=key):
                self.assertIn(key,self.catalog)
                self.assertTrue(all(self.catalog[key]))
                self.assertFalse(re.search(r'[\u4e00-\u9fff]',self.catalog[key][0]))
    def test_sms_and_confirmation_protocol_are_not_translated(self):
        self.assertIn("body.textContent=m.message",self.page)
        self.assertIn("number.textContent=m.number",self.page)
        self.assertIn("confirmation:'覆盖固件'",self.page)
        self.assertIn("confirmation:'永久清空已删除短信'",self.page)
        self.assertIn("var language='zh-CN'",self.page)
        self.assertIn('股票代码：832571',self.page)
