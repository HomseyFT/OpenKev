const playButton = document.getElementById('playButton');
const browseButton = document.getElementById('browseButton');
const featuredVideo = document.getElementById('featuredVideo');
const videoTitle = document.getElementById('videoTitle');
const videoDescription = document.getElementById('videoDescription');
const videoPlayButton = document.getElementById('videoPlayButton');

const updateFeaturedVideo = (card, play = false) => {
  if (!card || !featuredVideo) return;

  const videoUrl = card.dataset.video;
  const title = card.dataset.title ?? 'KevFlix Feature';
  const description = card.dataset.description ?? 'Enjoy this preview.';

  if (videoUrl) {
    featuredVideo.src = videoUrl;
    featuredVideo.load();
    if (play) {
      featuredVideo.play().catch(() => {});
    }
  }

  videoTitle.textContent = title;
  videoDescription.textContent = description;
};

if (playButton && featuredVideo) {
  playButton.addEventListener('click', () => {
    featuredVideo.scrollIntoView({ behavior: 'smooth', block: 'center' });
    featuredVideo.play().catch(() => {});
  });
}

if (browseButton) {
  browseButton.addEventListener('click', () => {
    const browseSection = document.getElementById('browse');
    browseSection?.scrollIntoView({ behavior: 'smooth' });
  });
}

const cards = document.querySelectorAll('.card[data-video]');
cards.forEach((card) => {
  card.addEventListener('click', () => updateFeaturedVideo(card, true));
  const watchButton = card.querySelector('.watch-button');
  watchButton?.addEventListener('click', (event) => {
    event.stopPropagation();
    updateFeaturedVideo(card, true);
  });
});

window.addEventListener('DOMContentLoaded', () => {
  const mascotPlaceholder = document.querySelector('.mascot-image-placeholder');
  if (mascotPlaceholder) {
    mascotPlaceholder.classList.add('highlight');
    setTimeout(() => mascotPlaceholder.classList.remove('highlight'), 1200);
  }

  const cards = document.querySelectorAll('.card[data-image]');
  cards.forEach((card) => {
    const imageUrl = card.dataset.image;
    const cardImage = card.querySelector('.card-image');
    if (imageUrl && cardImage) {
      cardImage.style.backgroundImage = `url('${imageUrl}')`;
    }
  });
});
