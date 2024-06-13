import abc
import re
import socket
import ssl
from datetime import datetime

import dns.resolver
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.db import models
from loguru import logger
import requests
from requests.exceptions import Timeout, ConnectionError, RequestException

from .plan import PlanDomain

# List of CNAMEs that are considered valid. Ensure they end with '.'.
ALLOWED_CNAMES: list[str] = [cn.strip('.').lower() + '.' for cn in  settings.DEPLOY_ALLOWED_CNAMES]


class DeployInfo(models.Model):
    """
    This is an abstract model class to hold deployment status information.
    """

    class DNSStatus(models.TextChoices):
        OK = 'ok', "All OK"
        DOES_NOT_EXIST = 'nxdomain', "Empty response"
        NOT_CNAME = 'not_cname', "Response is not CNAME"
        INVALID_TARGET = 'invalid_target', "CNAME target is not valid"
        OTHER_ERROR = 'other', "Other error"

    class TLSStatus(models.TextChoices):
        OK = 'ok', "All OK"
        INVALID_CA = 'invalid_ca', "Invalid CA"
        ABOUT_TO_EXPIRE = 'expiration', "Certificate expired or about to expire"
        OTHER_ERROR = 'other', "Other error"

    class HTTPStatus(models.TextChoices):
        OK = 'ok', "All OK"
        NETWORK_ERROR = 'network', "Network error"
        NOT_FOUND = '404', "Page not found (404)"
        SERVER_ERROR = '500', "Internal server error (500)"
        OTHER_ERROR = 'other', "Other error"

    created_at = models.DateTimeField(auto_now_add=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    dns_cname = models.CharField(max_length=100, null=True, blank=True)
    dns_status_msg = models.TextField(null=True, blank=True)
    dns_status = models.CharField(max_length=20, choices=DNSStatus.choices, null=True, blank=True)

    tls_expires_at = models.DateTimeField(null=True, blank=True)
    tls_status = models.CharField(max_length=20, choices=TLSStatus.choices, null=True, blank=True)
    tls_status_msg = models.TextField(null=True, blank=True)

    http_status = models.CharField(max_length=20, choices=HTTPStatus.choices, null=True, blank=True)
    http_status_msg = models.TextField(null=True, blank=True)

    STATUS_FIELDS = [
        'dns_cname', 'dns_status', 'dns_status_msg',
        'tls_expires_at', 'tls_status', 'tls_status_msg',
        'http_status', 'http_status_msg'
    ]

    class Meta:
        abstract = True
        ordering = ['-created_at']
        get_latest_by = 'created_at'

    @abc.abstractmethod
    def get_hostname(self) -> str: ...

    @abc.abstractmethod
    def get_path_prefix(self) -> str: ...

    def _is_cname_allowed(self, cname: str) -> bool:
        """Check for match against allowed CNAMEs.

        The allowed CNAMEs are regex expressions.
        """
        for allowed_cname in ALLOWED_CNAMES:
            if re.match(allowed_cname, cname):
                return True
        return False

    def check_dns(self):
        """
        Checks the DNS of the hostname.

        Specifically, it looks for CNAME records and validates the targets against a list of allowed CNAMEs.
        """
        self.dns_cname = None
        self.dns_status = self.DNSStatus.OTHER_ERROR
        self.dns_status_msg = None
        try:
            logger.info('Checking DNS for %s' % self.get_hostname())
            resp = dns.resolver.resolve(self.get_hostname(), 'A')
            logger.debug('Got DNS response for %s' % self.get_hostname())
        except dns.resolver.NXDOMAIN as e:
            logger.info('Got NXDOMAIN for %s' % self.get_hostname())
            self.dns_status = self.DNSStatus.DOES_NOT_EXIST
            self.dns_status_msg = str(e)
            return
        except Exception as e:
            logger.info('Unknown exception for %s: %s' % (self.get_hostname(), str(e)))
            self.dns_status_msg = str(e)
            return

        res = resp.chaining_result
        self.dns_status_msg = str(res.answer)

        if not len(res.cnames):
            self.dns_status = self.DNSStatus.NOT_CNAME
            logger.info('No CNAME records found for %s' % self.get_hostname())
            return

        cname_targets = [str(r.target).lower() for cn in res.cnames for r in cn]
        for cname in cname_targets:
            if cname in ALLOWED_CNAMES:
                # All good!
                self.dns_status = self.DNSStatus.OK
                logger.info('Found valid CNAME record for %s: %s' % (self.get_hostname(), cname))
                return
        else:
            self.dns_status = self.DNSStatus.INVALID_TARGET
            logger.info('Invalid CNAME target(s) found for %s: %s' % (self.get_hostname(), ', '.join(cname_targets)))

    def check_tls(self):
        """Connect to port 443, retrieve TLS certificate and check for validity + expiration."""

        self.tls_expires_at = None
        self.tls_status_msg = None
        self.tls_status = self.TLSStatus.OTHER_ERROR
        try:
            logger.info('Checking TLS for %s' % self.get_hostname())
            context = ssl.create_default_context()
            with socket.create_connection((self.get_hostname(), 443)) as sock:
                logger.debug('Connected to %s:443' % self.get_hostname())
                with context.wrap_socket(sock, server_hostname=self.get_hostname()) as ssock:
                    cert = ssock.getpeercert(binary_form=True)
                    logger.debug('Got TLS certificate for %s' % self.get_hostname())

            assert cert is not None
            cert_obj = x509.load_der_x509_certificate(cert, default_backend())
            not_after = cert_obj.not_valid_after

            issuer = cert_obj.issuer
            issuer_paths = [(attr.oid._name, str(attr.value, encoding='utf8') if not isinstance(attr.value, str) else attr.value) for attr in issuer]
            issuer_info = ', '.join(f'{attr[0]}={attr[1]}' for attr in issuer_paths)

            logger.info('Certificate for %s expires at %s (issued by %s)' % (self.get_hostname(), not_after, issuer_info))
            self.tls_expires_at = not_after
            self.tls_status_msg = f"Certificate issued by: {issuer_info}, expires at: {not_after}"
        except ssl.SSLCertVerificationError as e:
            self.tls_status = self.TLSStatus.INVALID_CA
            self.tls_status_msg = str(e)
            return
        except socket.gaierror as e:
            self.tls_status_msg = f"DNS resolution error: {str(e)}"
            return
        except ConnectionRefusedError as e:
            self.tls_status_msg = f"Connection refused: {str(e)}"
            return
        except Exception as e:
            self.tls_status_msg = str(e)
            return

        now = datetime.now()
        if now > not_after:
            self.tls_status = self.TLSStatus.ABOUT_TO_EXPIRE
            self.tls_status_msg = f"Certificate expired on {not_after}"
            return
        if (not_after - now).days < 15:
            self.tls_status = self.TLSStatus.ABOUT_TO_EXPIRE
            self.tls_status_msg = f"Certificate expires on {not_after}"
            return

        self.tls_status = self.TLSStatus.OK
        self.tls_status_msg = f"Certificate valid until {not_after}"

    def check_http(self):
        """Checks (with a HEAD request) if the hostname is reachable via HTTP (either port 80 or 443)."""

        self.http_status = self.HTTPStatus.OTHER_ERROR
        self.http_status_msg = None
        host_path = f'{self.get_hostname()}{self.get_path_prefix()}'
        if self.tls_status == self.TLSStatus.OK:
            # If TLS status is OK, use HTTPS
            proto = 'https'
        else:
            # If TLS status is not OK, check HTTP instead
            proto = 'http'

        url = '%s://%s' % (proto, host_path)
        logger.info('Checking %s' % (url))
        try:
            response = requests.head(url, allow_redirects=True, timeout=10)
        except (Timeout, ConnectionError, RequestException) as e:
            logger.error(f'HTTP(S) check failed for {url}: {type(e).__name__} - {str(e)}')
            self.http_status = self.HTTPStatus.NETWORK_ERROR if isinstance(e, (Timeout, ConnectionError)) else self.HTTPStatus.OTHER_ERROR
            self.http_status_msg = f"{type(e).__name__}: {str(e)}"
            return
        except Exception as e:
            logger.error(f'HTTP(S) check failed for {url}: Unknown error - {str(e)}')
            self.http_status = self.HTTPStatus.OTHER_ERROR
            self.http_status_msg = f"Unknown error: {str(e)}"
            return
        if response.status_code == 200:
            # All is well.
            logger.info('HTTP(S) check successful for %s' % url)
            self.http_status = self.HTTPStatus.OK
            return

        if response.status_code == 404:
            logger.warning('HTTP(S) check returned 404 for %s' % url)
            self.http_status = self.HTTPStatus.NOT_FOUND
        elif response.status_code >= 500:
            logger.error('HTTP(S) check returned server error for %s: %s' % (url, response.status_code))
            self.http_status = self.HTTPStatus.SERVER_ERROR
            self.http_status_msg = f"Server error: {response.status_code}"
        else:
            logger.warning('HTTP(S) check returned unexpected status code for %s: %s' % (url, response.status_code))
            self.http_status = self.HTTPStatus.OTHER_ERROR
            self.http_status_msg = f"Unexpected status code: {response.status_code}"

    def check_all(self):
        self.dns_status = self.tls_status = self.http_status = None
        self.check_dns()
        if self.dns_status != self.DNSStatus.OK:
            return
        self.check_tls()
        self.check_http()

    def statuses_changed(self, old_info: 'DeployInfo') -> bool:
        for field in self.STATUS_FIELDS:
            if getattr(self, field) != getattr(old_info, field):
                return True
        return False


class PlanDomainDeployInfo(DeployInfo):
    domain = models.ForeignKey(PlanDomain, on_delete=models.CASCADE, related_name='deploy_infos')

    def get_hostname(self):
        return self.domain.hostname

    def get_path_prefix(self) -> str:
        return self.domain.base_path or '/'
