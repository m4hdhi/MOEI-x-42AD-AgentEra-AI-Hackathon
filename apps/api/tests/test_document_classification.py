from app.routes.documents import classify_document


def test_classifies_emirates_id_from_uae_id_number_and_identity_fields():
    result = classify_document(
        {
            "document_type": "other",
            "full_name": "Ali Al Rumaithi",
            "id_number": "784-1988-1234567-1",
            "nationality": "United Arab Emirates",
            "expiry_date": "2030-01-01",
        },
        filename="emirates-id-front.jpg",
    )

    assert result["document_type"] == "emirates_id"
    assert result["confidence"] >= 0.75
    assert "uae_id_number_format:784-YYYY-NNNNNNN-C" in result["signals"]


def test_classifies_salary_certificate_from_salary_and_employer_fields():
    result = classify_document(
        {
            "document_type": "salary_certificate",
            "full_name": "Mariam Al Mansouri",
            "employer": "Example Government Entity",
            "designation": "Engineer",
            "monthly_salary_aed": 22000,
            "other": {"heading": "Salary Certificate", "footer": "HR Department stamp and signature"},
        },
        filename="salary-certificate.png",
    )

    assert result["document_type"] == "salary_certificate"
    assert result["confidence"] >= 0.75
    assert "monthly_salary_field_present" in result["signals"]
