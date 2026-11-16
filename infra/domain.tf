# Endereço próprio do chat: olist-chat.tuanyfortunato.com.br.
#
# A zona DNS de tuanyfortunato.com.br é do repositório do site pessoal, que a
# criou no bootstrap e a protege contra destruição. Aqui ela só é lida, e este
# projeto cria apenas os próprios registros. Assim o teardown do chat apaga
# esses registros e o certificado, mas não mexe na zona nem no site pessoal.

data "aws_route53_zone" "main" {
  name = var.zone_name
}

# Certificado HTTPS do subdomínio. O CloudFront só aceita certificados do ACM
# emitidos em us-east-1, a mesma região do restante do projeto.
resource "aws_acm_certificate" "app" {
  domain_name       = var.app_domain
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# O ACM confirma que o domínio é nosso procurando este registro na zona
resource "aws_route53_record" "certificate_validation" {
  for_each = {
    for option in aws_acm_certificate.app.domain_validation_options :
    option.domain_name => option
  }

  zone_id         = data.aws_route53_zone.main.zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 300
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "app" {
  certificate_arn         = aws_acm_certificate.app.arn
  validation_record_fqdns = [for record in aws_route53_record.certificate_validation : record.fqdn]
}

# O subdomínio aponta para o CloudFront, em IPv4 (A) e IPv6 (AAAA)
resource "aws_route53_record" "app" {
  for_each = toset(["A", "AAAA"])

  zone_id = data.aws_route53_zone.main.zone_id
  name    = var.app_domain
  type    = each.value

  alias {
    name                   = aws_cloudfront_distribution.main.domain_name
    zone_id                = aws_cloudfront_distribution.main.hosted_zone_id
    evaluate_target_health = false
  }
}
