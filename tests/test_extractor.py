from __future__ import annotations

from proxyscraper.harvest.extractor import (
    extract_from_html,
    extract_proxies,
    is_private_ip,
    is_valid_ipv4,
    is_valid_port,
    TableExtractor,
)


class TestValidation:
    def test_valid_ipv4(self):
        assert is_valid_ipv4("1.2.3.4") is True
        assert is_valid_ipv4("255.255.255.255") is True
        assert is_valid_ipv4("0.0.0.0") is True

    def test_invalid_ipv4(self):
        assert is_valid_ipv4("256.1.1.1") is False
        assert is_valid_ipv4("1.2.3") is False
        assert is_valid_ipv4("abc.def.ghi.jkl") is False
        assert is_valid_ipv4("") is False

    def test_private_ip(self):
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("169.254.1.1") is True

    def test_public_ip(self):
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.2.3.4") is False
        assert is_private_ip("203.0.113.1") is False

    def test_valid_port(self):
        assert is_valid_port(80) is True
        assert is_valid_port(1) is True
        assert is_valid_port(65535) is True

    def test_invalid_port(self):
        assert is_valid_port(0) is False
        assert is_valid_port(65536) is False
        assert is_valid_port(-1) is False


class TestExtractProxies:
    def test_basic_colon_format(self):
        text = "Proxy: 1.2.3.4:8080 and 5.6.7.8:3128"
        result = extract_proxies(text)
        assert (("1.2.3.4", 8080)) in result
        assert (("5.6.7.8", 3128)) in result

    def test_space_separated(self):
        text = "1.2.3.4 8080"
        result = extract_proxies(text)
        assert ("1.2.3.4", 8080) in result

    def test_deduplication(self):
        text = "1.2.3.4:8080 1.2.3.4:8080 1.2.3.4:8080"
        result = extract_proxies(text)
        assert len(result) == 1

    def test_filters_private_ips(self):
        text = "10.0.0.1:8080 192.168.1.1:3128 8.8.8.8:80"
        result = extract_proxies(text)
        assert len(result) == 1
        assert result[0] == ("8.8.8.8", 80)

    def test_allow_private(self):
        text = "10.0.0.1:8080"
        result = extract_proxies(text, allow_private=True)
        assert len(result) == 1

    def test_filters_invalid_octets(self):
        text = "999.999.999.999:8080"
        result = extract_proxies(text)
        assert len(result) == 0

    def test_filters_invalid_port(self):
        text = "1.2.3.4:0 5.6.7.8:99999"
        result = extract_proxies(text)
        assert len(result) == 0

    def test_empty_input(self):
        assert extract_proxies("") == []
        assert extract_proxies("no proxies here") == []

    def test_mixed_content(self):
        text = """
        Some text before
        Server 1: 45.67.89.10:8080
        Server 2: 123.45.67.89:3128
        Invalid: not.an.ip:1234
        More text
        """
        result = extract_proxies(text)
        assert len(result) == 2


class TestExtractFromHtml:
    def test_html_table(self):
        html = """
        <html><body>
        <table>
        <tr><td>45.67.89.10</td><td>8080</td></tr>
        <tr><td>123.45.67.89</td><td>3128</td></tr>
        </table>
        </body></html>
        """
        result = extract_from_html(html)
        assert len(result) == 2

    def test_html_with_tags(self):
        html = "<p>Proxy: <b>1.2.3.4</b>:<i>8080</i></p>"
        result = extract_from_html(html)
        assert ("1.2.3.4", 8080) in result

    def test_plain_text_in_html(self):
        html = "<pre>1.2.3.4:8080\n5.6.7.8:3128</pre>"
        result = extract_from_html(html)
        assert len(result) == 2


class TestTableExtractor:
    def test_table_extraction(self):
        html = """
        <table>
        <tr><td>45.67.89.10</td><td>8080</td><td>HTTP</td></tr>
        <tr><td>123.45.67.89</td><td>3128</td><td>SOCKS5</td></tr>
        </table>
        """
        extractor = TableExtractor()
        result = extractor.extract(html)
        assert len(result) == 2
        assert ("45.67.89.10", 8080) in result
