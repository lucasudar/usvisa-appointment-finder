import datetime
import time
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from creds import username, password, facility_name, latest_notification_date, seconds_between_checks
from telegram import send_message, send_photo
from urls import SIGN_IN_URL, SCHEDULE_URL, APPOINTMENTS_URL

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def log_in(driver):
    if driver.current_url != SIGN_IN_URL:
        return

    print('Logging in.')

    ok_button = driver.find_element(
        By.XPATH, '/html/body/div[7]/div[3]/div/button')
    if ok_button:
        ok_button.click()

    user_box = driver.find_element(By.NAME, 'user[email]')
    user_box.send_keys(username)
    password_box = driver.find_element(By.NAME, 'user[password]')
    password_box.send_keys(password)

    driver.find_element(
        By.XPATH, '//*[@id="sign_in_form"]/div[3]/label/div').click()

    driver.find_element(By.XPATH, '//*[@id="sign_in_form"]/p[1]/input').click()

    time.sleep(2)
    print('Logged in.')


def is_worth_notifying(year, month, days):
    first_available_date_object = datetime.datetime.strptime(
        f'{year}-{month}-{days[0]}', "%Y-%B-%d")
    latest_notification_date_object = datetime.datetime.strptime(
        latest_notification_date, '%Y-%m-%d')

    return first_available_date_object <= latest_notification_date_object


def check_appointments(driver):
    driver.get(SCHEDULE_URL)
    log_in(driver)

    driver.get(APPOINTMENTS_URL)

    continue_button = driver.find_element(By.CLASS_NAME, 'primary')
    if continue_button and continue_button.get_property('value') == 'Continue':
        continue_button.click()

    facility_select = WebDriverWait(driver, 2).until(EC.presence_of_element_located(
        (By.ID, 'appointments_consulate_appointment_facility_id')))
    facility_select = Select(facility_select)
    facility_select.select_by_visible_text(facility_name)
    time.sleep(1)

    if driver.find_element(By.ID, 'consulate_date_time_not_available').is_displayed():
        print("No dates available")
        return False

    date_picker = WebDriverWait(driver, 2).until(EC.element_to_be_clickable(
        (By.ID, 'appointments_consulate_appointment_date')))
    date_picker.click()

    while True:
        for date_picker in driver.find_elements(By.CLASS_NAME, 'ui-datepicker-group'):
            day_elements = date_picker.find_elements(By.TAG_NAME, 'td')
            available_days = [day_element.find_element(By.TAG_NAME, 'a').get_attribute("textContent")
                              for day_element in day_elements if day_element.get_attribute("class") == ' undefined']
            if available_days:
                month = date_picker.find_element(
                    By.CLASS_NAME, 'ui-datepicker-month').get_attribute("textContent")
                year = date_picker.find_element(
                    By.CLASS_NAME, 'ui-datepicker-year').get_attribute("textContent")
                message = f'Available days found in {month} {year}: {
                    ", ".join(available_days)}. Link: {SIGN_IN_URL}'
                print(message)

                if not is_worth_notifying(year, month, available_days):
                    print("Not worth notifying.")
                    return False

                for day_element in day_elements:
                    if day_element.get_attribute("class") == ' undefined':
                        day_element.find_element(By.TAG_NAME, 'a').click()
                        break

                time_picker = WebDriverWait(driver, 2).until(EC.element_to_be_clickable(
                    (By.ID, 'appointments_consulate_appointment_time')))
                time_picker.click()

                def wait_for_options(driver):
                    select = Select(driver.find_element(
                        By.ID, 'appointments_consulate_appointment_time'))
                    options = select.options
                    return len(options) > 1 and any(opt.text.strip() for opt in options)

                WebDriverWait(driver, 2).until(wait_for_options)

                time_select = Select(driver.find_element(
                    By.ID, 'appointments_consulate_appointment_time'))
                options = time_select.options

                if len(options) > 1:
                    time_select.select_by_index(1)

                continue_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, 'primary'))
                )
                continue_button.click()

                confirm_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable(
                        (By.CSS_SELECTOR, 'a.button.alert'))
                )
                confirm_button.click()

                send_message(message)
                send_photo(driver.get_screenshot_as_png())
                return True

        driver.find_element(By.CLASS_NAME, 'ui-datepicker-next').click()
        driver.find_element(By.CLASS_NAME, 'ui-datepicker-next').click()


def main():
    chrome_options = Options()
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation"])
    # chrome_options.add_argument("--headless")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    while True:
        current_time = time.strftime('%a, %d %b %Y %H:%M:%S', time.localtime())
        print(f'Starting a new check at {current_time}.')
        try:
            if check_appointments(driver):
                print("Appointment found and notification sent. Stopping the script.")
                driver.quit()
                sys.exit(0)
        except Exception as err:
            print(f'Exception: {err}')

        time.sleep(seconds_between_checks)


if __name__ == "__main__":
    main()
