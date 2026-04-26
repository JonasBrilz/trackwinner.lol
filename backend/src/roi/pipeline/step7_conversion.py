from ..models import UserInputs


def get_conversion_rates(inputs: UserInputs) -> tuple[float, float]:
    return inputs.visit_to_lead_rate, inputs.lead_to_customer_rate
